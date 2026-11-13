#Requires -Version 5.1
param([string]$Root = 'C:\SCStudioBackup')
$ErrorActionPreference = 'Stop'
$previous = $null
try {
    $previous = (Get-Content -LiteralPath (Join-Path $Root 'logs/status.json') -Raw | ConvertFrom-Json).lastSuccessUtc
} catch { }
# Preserve the existing backup, including local fixes, in its own process.
& (Join-Path $PSHOME 'powershell.exe') -NoProfile -NonInteractive -ExecutionPolicy RemoteSigned -File (Join-Path $PSScriptRoot 'Backup.ps1') -Root $Root
$backupCode = $LASTEXITCODE
if ($backupCode -eq 0) {
    try {
        $current = Get-Content -LiteralPath (Join-Path $Root 'logs/status.json') -Raw | ConvertFrom-Json
        if ($current.state -ne 'success' -or -not $current.lastSuccessUtc -or $current.lastSuccessUtc -eq $previous) {
            throw 'Nessun nuovo backup riuscito: segnale non inviato.'
        }
        Import-Module (Join-Path $PSScriptRoot 'StudioMonitor.psm1') -Force
        Send-StudioBackupSignal $Root
    } catch {
        Write-Warning 'Monitor non completato. Il risultato del backup resta invariato.'
    }
}
exit $backupCode
