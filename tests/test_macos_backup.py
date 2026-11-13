"""No real database, private recovery key or Keychain entry is used here."""
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
from zoneinfo import ZoneInfo

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts/macos-backup"
spec = importlib.util.spec_from_file_location("macos_backup_tests", SCRIPTS / "backup.py")
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)
installer_spec = importlib.util.spec_from_file_location("macos_installer_tests", SCRIPTS / "install.py")
installer = importlib.util.module_from_spec(installer_spec)
installer_spec.loader.exec_module(installer)


@pytest.fixture
def root(tmp_path, monkeypatch):
    old_mask = os.umask(0o077)
    monkeypatch.setattr(backup, "local_zone", lambda: ZoneInfo("Europe/Rome"))
    try:
        yield backup.prepare_root(tmp_path.resolve() / "SCStudioBackup")
    finally:
        os.umask(old_mask)


def fake_archive(root, when, name="sc-studio-20260101T000000Z-abcdef01", bucket="giornalieri"):
    path = root / "archivi" / bucket / name
    path.mkdir(mode=0o700)
    encrypted = path / "backup.dump.age"
    encrypted.write_bytes(b"synthetic ciphertext only")
    digest = backup.checksum(encrypted)
    (path / "backup.dump.age.sha256").write_text(digest + "  backup.dump.age\n")
    backup.save_json(path / "manifest.json", {
        "schemaVersion": 1, "format": "pg-custom-age-v1", "createdUtc": when.isoformat(),
        "bytes": encrypted.stat().st_size, "sha256": digest,
    })
    return path


def test_private_paths_and_lock(root):
    with pytest.raises(backup.BackupError):
        backup.prepare_root(root.parent / "wrong")
    link = root / "linked"
    link.symlink_to(root / "logs", target_is_directory=True)
    with pytest.raises(backup.BackupError):
        backup.safe_path(link / "file")
    with backup.lock(root):
        with pytest.raises(backup.BackupError):
            with backup.lock(root):
                pass


def test_preparation_failure_updates_status(root, monkeypatch):
    previous = "2026-10-21T21:00:00+00:00"
    backup.save_json(root / "logs/status.json", {"state": "success", "lastSuccessUtc": previous})
    monkeypatch.setattr(backup.sys, "argv", ["backup.py", "--root", str(root)])
    monkeypatch.setattr(backup, "load_configuration", lambda path: (_ for _ in ()).throw(backup.BackupError()))
    assert backup.main() == 1
    status = backup.read_status(root)
    assert status["state"] == "error"
    assert status["stage"] == "preparazione"
    assert status["lastSuccessUtc"] == previous


def test_credential_never_appears_in_arguments(root, monkeypatch, capsys):
    secret = "SyntheticOnlyPassword0123456789ABC"
    calls = []
    monkeypatch.setattr(installer.backup, "load_configuration", lambda path: {})
    monkeypatch.setattr(installer.backup, "preflight", lambda cfg: None)
    monkeypatch.setattr(installer.backup, "keychain_password", lambda: secret)

    def invoke(arguments, **kwargs):
        calls.append((arguments, kwargs))
        assert all(secret not in item for item in arguments)
        if "find-generic-password" in arguments:
            return subprocess.CompletedProcess(arguments, 44, b"", b"")
        if arguments[0] == "/usr/bin/osascript":
            return subprocess.CompletedProcess(arguments, 0, (secret + "\n").encode(), b"")
        return subprocess.CompletedProcess(arguments, 0, b"", b"")

    monkeypatch.setattr(installer.subprocess, "run", invoke)
    installer.save_credential(root)
    output = capsys.readouterr()
    assert secret not in output.out + output.err
    store = calls[-1]
    assert store[0] == ["/usr/bin/security", "-i"]
    assert secret.encode() in store[1]["input"]
    assert b"-T /usr/bin/security" in store[1]["input"]
    assert b" -A " not in store[1]["input"]


def test_permissions_and_status_path_escape(root):
    with pytest.raises(backup.BackupError):
        backup.archive_from_status(root, {"archive": "../../foreign"})
    (root / "logs/public.json").write_text("{}")
    (root / "logs/public.json").chmod(0o644)
    with pytest.raises(backup.BackupError):
        backup.read_json(root / "logs/public.json")


def test_corruption_foreign_files_and_retention(root):
    now = datetime(2026, 10, 21, 21, tzinfo=timezone.utc)
    expired = fake_archive(root, now - timedelta(days=15))
    fresh = fake_archive(root, now, "sc-studio-20261021T210000Z-abcdef02")
    foreign = root / "archivi/giornalieri/not-our-archive"
    foreign.mkdir(mode=0o700)
    (foreign / "keep").write_text("keep")
    backup.retain(root, now)
    assert not expired.exists()
    assert fresh.exists() and foreign.exists()
    (fresh / "backup.dump.age").write_bytes(b"corrupt")
    with pytest.raises(backup.BackupError):
        backup.verify_archive(fresh)
    with pytest.raises(backup.BackupError):
        backup.retain(root, now)
    assert fresh.exists()


def test_extra_file_protects_archive_from_deletion(root):
    now = datetime(2026, 10, 21, tzinfo=timezone.utc)
    path = fake_archive(root, now - timedelta(days=100))
    (path / "unrelated.txt").write_text("keep")
    with pytest.raises(backup.BackupError):
        backup.retain(root, now)
    assert (path / "unrelated.txt").exists()


def test_calendar_due_catchup_dst_and_failure_retry(root):
    # 26 October is CET, but the previous scheduled 22:00 on 24 October was CEST.
    last = datetime(2026, 10, 24, 20, 5, tzinfo=timezone.utc)
    path = fake_archive(root, last)
    backup.write_status(root, "success", "completato", {},
                        str(path.relative_to(root)), last)
    assert not backup.due(root, datetime(2026, 10, 25, 10, tzinfo=timezone.utc))
    assert backup.due(root, datetime(2026, 10, 25, 21, tzinfo=timezone.utc))
    backup.write_status(root, "error", "dump", backup.read_status(root))
    assert backup.due(root, datetime(2026, 10, 25, 10, tzinfo=timezone.utc))
    assert backup.read_status(root)["lastSuccessUtc"] == last.isoformat()


def test_status_recent_check_and_future_clock(root):
    now = datetime(2026, 10, 21, 21, tzinfo=timezone.utc)
    path = fake_archive(root, now)
    backup.write_status(root, "success", "completato", {}, str(path.relative_to(root)), now)
    backup.check(root, now + timedelta(minutes=5))
    with pytest.raises(backup.BackupError):
        backup.check(root, now + timedelta(hours=25))
    assert backup.due(root, now - timedelta(hours=1))


def test_environment_has_no_inherited_pg_secrets(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "synthetic-secret")
    monkeypatch.setenv("PGPASSWORD", "synthetic-secret")
    monkeypatch.setenv("PGSERVICE", "unrelated")
    env = backup.child_environment({"PGHOST": "example.render.com"})
    assert "DATABASE_URL" not in env and "PGPASSWORD" not in env and "PGSERVICE" not in env
    assert env["PGHOST"] == "example.render.com"
    with pytest.raises(backup.BackupError) as error:
        backup.tool(["/bin/sh", "-c", "echo synthetic-secret >&2; exit 1"])
    assert "synthetic-secret" not in str(error.value)


def test_dump_failure_preserves_previous_and_cleans_work(root, monkeypatch):
    now = datetime(2026, 10, 21, 21, tzinfo=timezone.utc)
    path = fake_archive(root, now)
    backup.write_status(root, "success", "completato", {}, str(path.relative_to(root)), now)
    cfg = dict(host="synthetic.render.com", port=5432, database="synthetic", user="studio_backup",
               sslRootCert="synthetic.pem", pgDump="synthetic", pgRestore="synthetic", age="synthetic")
    monkeypatch.setattr(backup, "tool", lambda *args, **kwargs: (_ for _ in ()).throw(backup.BackupError("failure")))
    assert backup.run_backup(root, cfg, now + timedelta(minutes=1), lambda: "synthetic") == 1
    assert backup.read_status(root)["lastSuccessUtc"] == now.isoformat()
    assert backup.read_status(root)["stage"] == "dump"
    assert not list((root / ".work").iterdir())


@pytest.mark.parametrize("failure", ["portachiavi", "dump", "verifica_dump", "cifratura"])
def test_failure_and_retry_preserve_old_backup(root, monkeypatch, failure):
    now = datetime(2026, 10, 22, 21, tzinfo=timezone.utc)
    current_time = now

    class FixedClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return current_time.astimezone(tz) if tz else current_time.replace(tzinfo=None)

    # Status timestamps use the completion clock, separate from archive creation.
    monkeypatch.setattr(backup, "datetime", FixedClock)
    previous = now - timedelta(days=1)
    old = fake_archive(root, previous)
    backup.write_status(root, "success", "completato", {}, str(old.relative_to(root)), previous)
    cfg = dict(host="synthetic.render.com", port=5432, database="synthetic", user="studio_backup",
               sslRootCert="synthetic.pem", pgDump="synthetic_dump", pgRestore="synthetic_restore",
               age="synthetic_age", recipient="synthetic")
    failed = True

    def password():
        if failed and failure == "portachiavi":
            raise backup.BackupError()
        return "synthetic-only"

    def native(arguments, *args, **kwargs):
        stage = {"synthetic_dump": "dump", "synthetic_restore": "verifica_dump",
                 "synthetic_age": "cifratura"}[arguments[0]]
        if failed and failure == stage:
            raise backup.BackupError()
        if stage == "dump":
            Path(arguments[arguments.index("--file") + 1]).write_bytes(b"synthetic dump")
        elif stage == "cifratura":
            Path(arguments[arguments.index("--output") + 1]).write_bytes(b"synthetic ciphertext")
        return b""

    monkeypatch.setattr(backup, "tool", native)
    assert backup.run_backup(root, cfg, now, password) == 1
    status = backup.read_status(root)
    assert status["state"] == "error" and status["stage"] == failure
    assert status["lastSuccessUtc"] == previous.isoformat()
    assert backup.due(root, now)
    assert not list((root / ".work").iterdir())
    backup.verify_archive(old)
    failed = False
    current_time = now + timedelta(minutes=1)
    assert backup.run_backup(root, cfg, now + timedelta(minutes=1), password) == 0
    backup.check(root, now + timedelta(minutes=2))
    backup.verify_archive(old)
    assert not list((root / ".work").iterdir())


def test_disk_full_does_not_read_credentials(root, monkeypatch):
    from collections import namedtuple
    Usage = namedtuple("Usage", "total used free")
    monkeypatch.setattr(backup.shutil, "disk_usage", lambda path: Usage(100, 99, 1))

    def forbidden():
        pytest.fail("Credentials must not be read when free space is insufficient")

    assert backup.run_backup(root, {}, datetime.now(timezone.utc), forbidden) == 1
    assert backup.read_status(root)["stage"] == "spazio"


@pytest.mark.parametrize("reply", [b"OK", b"OK (not found)"])
def test_monitor_empty_signal_and_failure_isolation(root, monkeypatch, reply):
    now = datetime.now(timezone.utc)
    archive = fake_archive(root, now)
    backup.write_status(root, "success", "completato", {}, str(archive.relative_to(root)), now)
    original = backup.read_status(root)
    backup.save_json(root / "config/monitor.json", {"enabled": True})
    endpoint = "https://hc-ping.com/00000000-0000-0000-0000-000000000001"
    monkeypatch.setattr(backup, "tool", lambda *a, **kw: endpoint.encode())
    requests = []

    class Connection:
        def __init__(self, host, timeout, context):
            assert host == "hc-ping.com" and timeout == 8
            assert context.verify_mode == backup.ssl.CERT_REQUIRED

        def request(self, method, path, body, headers):
            requests.append((method, path, body))

        def getresponse(self):
            from types import SimpleNamespace
            return SimpleNamespace(status=200, read=lambda length: reply)

        def close(self):
            pass

    monkeypatch.setattr(backup.http.client, "HTTPSConnection", Connection)
    backup.signal_new_backup(root)
    assert requests == [("POST", "/00000000-0000-0000-0000-000000000001", b"")]
    assert backup.read_status(root) == original
    assert backup.read_json(root / "logs/monitor.json")["state"] == ("success" if reply == b"OK" else "error")


def test_monitor_disabled_and_rejects_other_destinations(root, monkeypatch):
    monkeypatch.setattr(backup, "tool", lambda *a, **k: pytest.fail("No Keychain access without opt-in"))
    backup.signal_new_backup(root)
    for value in ("http://hc-ping.com/00000000-0000-0000-0000-000000000001",
                  "https://example.org/secret", "https://hc-ping.com@evil.example/secret"):
        with pytest.raises(backup.BackupError):
            backup.monitor_path(value)


@pytest.mark.parametrize("mode,result,expected", [([], 0, 1), ([], 1, 0), ([], 2, 0),
                                                 (["--scheduled"], 0, 0), (["--check"], 0, 0),
                                                 (["--preflight"], 0, 0)])
def test_monitor_not_refreshed_by_failed_or_skipped_runs(root, monkeypatch, mode, result, expected):
    signals = []
    monkeypatch.setattr(backup.sys, "argv", ["backup.py", "--root", str(root), *mode])
    monkeypatch.setattr(backup, "load_configuration", lambda root: {})
    monkeypatch.setattr(backup, "preflight", lambda cfg: None)
    monkeypatch.setattr(backup, "check", lambda *args: None)
    monkeypatch.setattr(backup, "due", lambda *args: False)
    monkeypatch.setattr(backup, "run_backup", lambda *args: result)
    monkeypatch.setattr(backup, "signal_new_backup", lambda root: signals.append(True))
    backup.main()
    assert len(signals) == expected


def test_independent_daily_weekly_monthly_publication(root):
    now = datetime(2026, 11, 1, 21, tzinfo=timezone.utc)  # Sunday, local 22:00.
    work = root / ".work/synthetic"
    work.mkdir(mode=0o700)
    original = fake_archive(root, now)
    staging = work / "publish"
    shutil.copytree(original, staging)
    relative = backup.publish(root, staging, now)
    name = Path(relative).name
    paths = [root / "archivi" / bucket / name / "backup.dump.age"
             for bucket in ("giornalieri", "settimanali", "mensili")]
    assert len({path.stat().st_ino for path in paths}) == 3
    paths[0].write_bytes(b"corrupt")
    assert paths[1].read_bytes() == b"synthetic ciphertext only"


def test_launch_agent_no_secrets_and_sleep_recovery(root):
    data = installer.agent_definition(root)
    decoded = plistlib.loads(plistlib.dumps(data))
    assert decoded["RunAtLoad"] is True and decoded["StartInterval"] == 3600
    assert decoded["StartCalendarInterval"] == {"Hour": 22, "Minute": 0}
    assert decoded["Umask"] == 0o077
    assert "--scheduled" in decoded["ProgramArguments"]
    source = "\n".join(path.read_text() for path in SCRIPTS.glob("*.py"))
    assert "googleapis.com" not in source and "import app" not in source
    assert "find-generic-password" in source


def test_real_crypto_and_restore_on_disposable_postgres(root, tmp_path):
    host = os.environ.get("STUDIO_MAC_TEST_PGHOST", "")
    if not host:
        pytest.skip("Dedicated disposable PostgreSQL socket not configured.")
    assert host.startswith("/private/tmp/studio-mac-backup-pg.")
    from sqlalchemy import Integer, String, create_engine, select
    from sqlalchemy.engine import URL
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

    class Base(DeclarativeBase):
        pass

    class SyntheticRecord(Base):
        __tablename__ = "synthetic_mac_backup_record"
        id: Mapped[int] = mapped_column(Integer, primary_key=True)
        label: Mapped[str] = mapped_column(String(40))

    def engine(name):
        assert name in {"studio_mac_backup_test_source", "studio_mac_backup_test_restore"}
        return create_engine(URL.create("postgresql+psycopg", username="studio_backup_test_user", database=name,
                                       query={"host": host, "port": "55542"}))

    source, destination = engine("studio_mac_backup_test_source"), engine("studio_mac_backup_test_restore")
    identity = tmp_path / "synthetic.agekey"
    native_env = backup.child_environment({"PGHOST": host, "PGPORT": "55542", "PGUSER": "studio_backup_test_user"})
    try:
        subprocess.run(["/opt/homebrew/bin/age-keygen", "-o", str(identity)],
                       capture_output=True, check=True)
        recipient = subprocess.run(["/opt/homebrew/bin/age-keygen", "-y", str(identity)],
                                   capture_output=True, text=True, check=True).stdout.strip()
        Base.metadata.create_all(source)
        with Session(source) as session:
            session.add_all([SyntheticRecord(id=1, label="Synthetic alpha"), SyntheticRecord(id=2, label="Synthetic beta")])
            session.commit()
        cfg = dict(host=host, port=55542, user="studio_backup_test_user", database="studio_mac_backup_test_source",
                   pgDump="/opt/homebrew/bin/pg_dump", pgRestore="/opt/homebrew/bin/pg_restore",
                   age="/opt/homebrew/bin/age", sslRootCert="/etc/ssl/cert.pem", recipient=recipient)
        now = datetime.now(timezone.utc)
        assert backup.run_backup(root, cfg, now, lambda: "synthetic-no-secret") == 0
        backup.check(root, now)
        archive = backup.archive_from_status(root, backup.read_status(root))
        decrypted = tmp_path / "synthetic.dump"
        backup.tool([cfg["age"], "--decrypt", "--identity", str(identity), "--output", str(decrypted), str(archive / "backup.dump.age")])
        backup.tool([cfg["pgRestore"], "--no-owner", "--no-acl", "--single-transaction", "--dbname", "studio_mac_backup_test_restore", str(decrypted)], native_env)
        with Session(destination) as session:
            assert session.execute(select(SyntheticRecord.id, SyntheticRecord.label).order_by(SyntheticRecord.id)).all() == [(1, "Synthetic alpha"), (2, "Synthetic beta")]
        assert not list((root / ".work").iterdir())
        bad = tmp_path / "corrupt.age"
        ciphertext = bytearray((archive / "backup.dump.age").read_bytes())
        ciphertext[-1] ^= 1
        bad.write_bytes(ciphertext)
        with pytest.raises(backup.BackupError):
            backup.tool([cfg["age"], "--decrypt", "--identity", str(identity), "--output", str(tmp_path / "bad.dump"), str(bad)])
    finally:
        Base.metadata.drop_all(source)
        Base.metadata.drop_all(destination)
        source.dispose()
        destination.dispose()
