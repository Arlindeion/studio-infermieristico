#Requires -Version 5.1
param([string]$Root = 'C:\SCStudioBackup', [switch]$Check)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'StudioBackup.psm1') -Force
try {
    Assert-StudioWindows
    $Root = Get-StudioRoot $Root
    if ($Check) {
        Test-StudioBackupStatus $Root
        Write-Host 'Backup recente e integrita verificata. Questo controllo non si collega al database.'
        exit 0
    }
    $configuration = Get-StudioConfiguration $Root
    $credential = Import-Clixml -LiteralPath (Join-Path $Root 'config/database.credential.xml')
    if ($credential -isnot [Management.Automation.PSCredential]) { throw 'Credenziali non valide.' }
    $code = Invoke-StudioBackup $Root $configuration $credential
    if ($code -eq 0) { Write-Host 'Backup cifrato completato e verificato.' }
    else { Write-Warning 'Backup non completato oppure avviso di conservazione. Consultare logs/status.json.' }
    exit $code
} catch {
    # Never echo native errors, connection details, credentials or patient data.
    if (-not $Check) {
        try {
            $safeRoot = Get-StudioRoot $Root
            Assert-StudioPrivateAcl $safeRoot
            Assert-StudioPath (Join-Path $safeRoot 'logs')
            Assert-StudioPrivateAcl (Join-Path $safeRoot 'logs')
            Write-StudioStatus $safeRoot 'error' 'configurazione'
        } catch { }
    }
    Write-Warning 'Operazione fermata: verificare piattaforma, permessi, strumenti e configurazione dello stesso account Windows.'
    exit 1
}
