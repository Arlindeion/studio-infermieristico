#Requires -Version 5.1
param([Parameter(Mandatory)][string]$ArchiveDirectory, [Parameter(Mandatory)][string]$IdentityPath,
      [string]$Root = 'C:\SCStudioBackup')
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'StudioBackup.psm1') -Force
$work = $null
try {
    $configuration = Get-StudioConfiguration $Root
    [void](Test-StudioArchive $ArchiveDirectory)
    $work = New-StudioWorkDirectory $Root
    $dump = Join-Path $work 'verified.dump'
    [void](Invoke-StudioTool $configuration.age @('--decrypt', '--identity', $IdentityPath,
        '--output', $dump, (Join-Path $ArchiveDirectory 'backup.dump.age')))
    [void](Invoke-StudioTool (Join-Path $configuration.pgBin 'pg_restore.exe') @('--list', $dump))
    Write-Host 'Decifratura e struttura PostgreSQL verificate. Non e stato eseguito un ripristino nel database.'
} catch {
    Write-Warning 'Verifica fallita: controllare archivio, chiave e strumenti. Nessun database e stato modificato.'
    exit 1
} finally {
    if ($work -and [IO.Directory]::Exists($work)) { Remove-StudioWorkDirectory $Root $work }
}
