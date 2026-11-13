"""Opt-in executable acceptance suite; never accepts a production database URL."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

import pytest
from sqlalchemy import create_engine, Integer, String, select
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

ROOT = Path(__file__).resolve().parents[1]


def test_windows_backup_contains_no_application_integration_or_execution_policy_bypass():
    scripts = list((ROOT / 'scripts/windows-backup').glob('*.ps*1'))
    assert len(scripts) == 7
    for script in scripts:
        source = script.read_text()
        assert 'ExecutionPolicy Bypass' not in source
        assert 'Invoke-WebRequest' not in source
        assert 'googleapis.com' not in source
        assert 'Import-Module app' not in source


def test_windows_monitor_is_opt_in_success_only_and_has_no_failure_ping():
    runner = (ROOT / 'scripts/windows-backup/Backup-Monitored.ps1').read_text()
    module = (ROOT / 'scripts/windows-backup/StudioMonitor.psm1').read_text()
    setup = (ROOT / 'scripts/windows-backup/Enable-Monitor.ps1').read_text()
    assert "if ($backupCode -eq 0)" in runner and 'Send-StudioBackupSignal $Root' in runner
    assert '$current.lastSuccessUtc -eq $previous' in runner
    assert 'exit $backupCode' in runner
    assert 'Send-StudioBackupSignal' not in (ROOT / 'scripts/windows-backup/Backup.ps1').read_text()
    assert 'monitor.credential.xml' in module and 'Import-Clixml' in module
    assert "$request.AllowAutoRedirect = $false" in module
    assert "$request.Timeout = 8000" in module
    assert 'Export-Clixml' in setup and '-AsSecureString' in setup
    assert '/fail' not in module


@pytest.mark.parametrize('backup_code,new_success,signaled', [(0, True, True), (1, False, False), (0, False, False)])
def test_windows_monitor_wrapper_preserves_backup_exit_code(tmp_path, backup_code, new_success, signaled):
    pwsh = os.environ.get('STUDIO_TEST_PWSH')
    if not pwsh:
        pytest.skip('PowerShell runtime not configured.')
    folder = tmp_path.resolve()
    runtime = folder / 'scripts'
    runtime.mkdir()
    root = folder / 'SCStudioBackup'
    (root / 'logs').mkdir(parents=True)
    old = dict(state='success', lastSuccessUtc='2026-10-20T21:00:00Z')
    (root / 'logs/status.json').write_text(json.dumps(old))
    shutil_source = ROOT / 'scripts/windows-backup/Backup-Monitored.ps1'
    (runtime / 'Backup-Monitored.ps1').write_bytes(shutil_source.read_bytes())
    # Synthetic backup and sender: no real DB, DPAPI, endpoints or secrets.
    fake = 'param([string]$Root)\n'
    if new_success:
        fake += "@{ state='success'; lastSuccessUtc='2026-10-22T21:00:00Z' } | ConvertTo-Json | Set-Content (Join-Path $Root 'logs/status.json')\n"
    fake += f'exit {backup_code}\n'
    (runtime / 'Backup.ps1').write_text(fake)
    (runtime / 'StudioMonitor.psm1').write_text("function Send-StudioBackupSignal { param($Root) 'sent' | Set-Content (Join-Path $Root 'logs/signal') }; Export-ModuleMember -Function Send-StudioBackupSignal")
    # Map only the Windows child interpreter name to this platform's runtime.
    command = r"""function Join-Path {
        param($Path, $ChildPath)
        if ($Path -eq $PSHOME -and $ChildPath -eq 'powershell.exe') {
            return [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName
        }
        Microsoft.PowerShell.Management\Join-Path $Path $ChildPath
    }
    & '%s' -Root '%s'
    """ % (str(runtime / 'Backup-Monitored.ps1').replace("'", "''"), str(root).replace("'", "''"))
    result = subprocess.run([pwsh, '-NoProfile', '-NonInteractive', '-Command', command], capture_output=True, text=True, timeout=30)
    assert result.returncode == backup_code, result.stdout + result.stderr
    assert (root / 'logs/signal').exists() is signaled


def test_windows_backup_runtime_on_disposable_local_postgres():
    names = ('STUDIO_TEST_PWSH', 'STUDIO_TEST_AGE', 'STUDIO_TEST_KEYGEN',
             'STUDIO_TEST_PGBIN', 'STUDIO_TEST_PGHOST', 'STUDIO_TEST_PGUSER')
    if not all(os.environ.get(name) for name in names):
        pytest.skip('Dedicated PowerShell/age/local PostgreSQL acceptance environment not configured.')
    host = os.environ['STUDIO_TEST_PGHOST']
    assert host.startswith('/private/tmp/studio-win-backup-pg.')
    port = int(os.environ.get('STUDIO_TEST_PGPORT', '55441'))

    class Base(DeclarativeBase):
        pass

    class SyntheticRecord(Base):
        __tablename__ = 'synthetic_backup_record'
        id: Mapped[int] = mapped_column(Integer, primary_key=True)
        label: Mapped[str] = mapped_column(String(100))

    def engine_for(name):
        assert name in {'studio_windows_backup_test_source', 'studio_windows_backup_test_restore'}
        return create_engine(URL.create(
            'postgresql+psycopg', username=os.environ['STUDIO_TEST_PGUSER'], database=name,
            query={'host': host, 'port': str(port)},
        ))

    source = engine_for('studio_windows_backup_test_source')
    restored = engine_for('studio_windows_backup_test_restore')
    try:
        Base.metadata.create_all(source)
        with Session(source) as session:
            session.add_all([SyntheticRecord(id=1, label='Synthetic alpha'),
                             SyntheticRecord(id=2, label='Synthetic beta')])
            session.commit()
        with tempfile.TemporaryDirectory(prefix='sc-studio-windows-tests-') as temp_dir:
            completed = subprocess.run([
                os.environ['STUDIO_TEST_PWSH'], '-NoProfile', '-NonInteractive', '-File',
                str(ROOT / 'tests/windows/StudioBackup.Tests.ps1'), '-TestRoot', str(Path(temp_dir).resolve()),
                '-PgBin', os.environ['STUDIO_TEST_PGBIN'], '-Age', os.environ['STUDIO_TEST_AGE'],
                '-Keygen', os.environ['STUDIO_TEST_KEYGEN'], '-DatabaseHost', host,
                '-DatabasePort', str(port), '-DatabaseUser', os.environ['STUDIO_TEST_PGUSER'],
            ], capture_output=True, text=True, timeout=120)
            assert completed.returncode == 0, completed.stdout + completed.stderr
            assert 'PASS:' in completed.stdout
            print(completed.stdout.strip())
            result = json.loads((Path(temp_dir) / 'result.json').read_text())
            assert Path(result['archive']).is_dir()
            with Session(restored) as session:
                assert session.execute(select(SyntheticRecord.id, SyntheticRecord.label).order_by(SyntheticRecord.id)).all() == [
                    (1, 'Synthetic alpha'), (2, 'Synthetic beta')]
    finally:
        Base.metadata.drop_all(source)
        Base.metadata.drop_all(restored)
        source.dispose()
        restored.dispose()
