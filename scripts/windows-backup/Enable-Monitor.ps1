#Requires -Version 5.1
param([string]$Root = 'C:\SCStudioBackup')
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'StudioBackup.psm1') -Force
try {
    Assert-StudioWindows
    $Root = Get-StudioRoot $Root
    $path = Join-Path $Root 'config/monitor.credential.xml'
    Assert-StudioPath $path
    Assert-StudioPrivateAcl (Join-Path $Root 'config')
    if (Test-Path -LiteralPath $path) { throw 'Monitor gia configurato: non sovrascritto.' }
    $secret = Read-Host 'Incolla il Ping URL del SOLO controllo Backup Windows (non la password database)' -AsSecureString
    $credential = New-Object Management.Automation.PSCredential('healthchecks', $secret)
    $value = $credential.GetNetworkCredential().Password
    if ($value -cnotmatch '^https://hc-ping\.com/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$') { throw 'Destinazione non valida.' }
    $credential | Export-Clixml -LiteralPath $path
    Assert-StudioPrivateAcl $path
    Write-Host 'Monitor Windows configurato con DPAPI. Nessun segnale inviato: partira dopo un nuovo backup riuscito.'
} catch {
    Write-Warning 'Monitor non configurato. Nessun dettaglio riservato viene mostrato.'
    exit 1
} finally { $value = $null; $credential = $null; $secret = $null }
