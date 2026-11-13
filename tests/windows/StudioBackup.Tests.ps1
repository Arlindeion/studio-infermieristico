param([Parameter(Mandatory)][string]$TestRoot, [Parameter(Mandatory)][string]$PgBin,
      [Parameter(Mandatory)][string]$Age, [Parameter(Mandatory)][string]$Keygen,
      [Parameter(Mandatory)][string]$DatabaseHost, [int]$DatabasePort = 55441,
      [Parameter(Mandatory)][string]$DatabaseUser)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Import-Module (Join-Path $PSScriptRoot '../../scripts/windows-backup/StudioBackup.psm1') -Force
$script:checks = 0
function Assert-Check($Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
    $script:checks++
}
function Assert-Rejected([scriptblock]$Action, [string]$Message) {
    $rejected = $false
    try { & $Action | Out-Null } catch { $rejected = $true }
    Assert-Check $rejected $Message
}
if ([IO.Path]::GetFileName($TestRoot) -notlike 'sc-studio-windows-tests-*') { throw 'Test-only directory required.' }
if ($DatabaseHost -notmatch '^/private/tmp/studio-win-backup-pg\.[a-zA-Z0-9]+$' -and $DatabaseHost -notin @('127.0.0.1', 'localhost')) {
    throw 'Only an explicitly disposable local PostgreSQL instance is allowed.'
}
$root = Join-Path $TestRoot 'path with spaces/SCStudioBackup'
[void][IO.Directory]::CreateDirectory($root)
$identity = Join-Path $TestRoot 'synthetic-recovery.agekey'
[void](Invoke-StudioTool $Keygen @('--output', $identity))
$recipient = (Invoke-StudioTool $Keygen @('-y', $identity)).Trim()
$config = [pscustomobject]@{
    host = $DatabaseHost; port = $DatabasePort; database = 'studio_windows_backup_test_source'
    pgBin = $PgBin; age = $Age; recipient = $recipient
}
$secret = ConvertTo-SecureString 'synthetic-only-not-a-real-password' -AsPlainText -Force
$credential = New-Object Management.Automation.PSCredential($DatabaseUser, $secret)
$now = [datetime]::Parse('2026-11-01T12:00:00Z').ToUniversalTime()

foreach ($scriptFile in Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot '../../scripts/windows-backup') -File) {
    if ($scriptFile.Extension -notin @('.ps1', '.psm1')) { continue }
    $tokens = $null; $errors = $null
    [void][Management.Automation.Language.Parser]::ParseFile($scriptFile.FullName, [ref]$tokens, [ref]$errors)
    Assert-Check ($errors.Count -eq 0) ('Syntax error: ' + $scriptFile.Name)
}
Assert-Rejected { Get-StudioRoot '/' } 'Filesystem root accepted.'
Assert-Rejected { Get-StudioRoot 'relative/SCStudioBackup' } 'Relative path accepted.'
Assert-Rejected { Get-StudioRoot '\\server\share\SCStudioBackup' } 'UNC path accepted.'

$env:PGSERVICE = 'must-not-be-used'
$env:PGOPTIONS = '-c default_transaction_read_only=off'
$code = Invoke-StudioBackup $root $config $credential $now
Assert-Check ($code -eq 0) 'Real PostgreSQL backup failed.'
Assert-Check ($env:PGSERVICE -eq 'must-not-be-used') 'Parent environment modified.'
Remove-Item Env:PGSERVICE
Remove-Item Env:PGOPTIONS
$status = Get-Content -LiteralPath (Join-Path $root 'logs/status.json') -Raw | ConvertFrom-Json
$archive = Join-Path $root $status.archive
foreach ($bucket in @('giornalieri', 'settimanali', 'mensili')) {
    Assert-Check (@(Get-ChildItem -LiteralPath (Join-Path $root ('archivi/' + $bucket)) -Directory).Count -eq 1) ('Missing bucket: ' + $bucket)
}
Assert-Check (@(Get-ChildItem -LiteralPath (Join-Path $root '.work') -Directory).Count -eq 0) 'Plaintext work directory left behind.'
Test-StudioBackupStatus $root $now
$script:checks++

$raw = Join-Path $TestRoot 'synthetic-restored.dump'
[void](Invoke-StudioTool $Age @('--decrypt', '--identity', $identity, '--output', $raw, (Join-Path $archive 'backup.dump.age')))
[void](Invoke-StudioTool (Join-Path $PgBin 'pg_restore.exe') @('--list', $raw))
$script:checks++
$restoreEnv = @{
    PGHOST = $DatabaseHost; PGPORT = [string]$DatabasePort; PGUSER = $DatabaseUser
    PGDATABASE = 'studio_windows_backup_test_restore'; PGCONNECT_TIMEOUT = '5'
}
[void](Invoke-StudioTool (Join-Path $PgBin 'pg_restore.exe') @('--dbname=studio_windows_backup_test_restore', '--no-owner', '--no-acl', '--exit-on-error', '--single-transaction', $raw) $restoreEnv)
$script:checks++
Write-StudioJson (Join-Path $TestRoot 'result.json') @{ archive = $archive; identity = $identity }

$locked = [IO.File]::Open((Join-Path $root '.work/backup.lock'), [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
try { Assert-Check ((Invoke-StudioBackup $root $config $credential $now) -eq 3) 'Concurrent execution not rejected.' }
finally { $locked.Dispose() }

$bad = $config.PSObject.Copy()
$bad.age = Join-Path $TestRoot 'missing-age'
Assert-Check ((Invoke-StudioBackup $root $bad $credential $now) -eq 1) 'Encryption failure accepted.'
$failedStatus = Get-Content -LiteralPath (Join-Path $root 'logs/status.json') -Raw | ConvertFrom-Json
Assert-Check ($failedStatus.stage -eq 'cifratura' -and $failedStatus.state -eq 'error') 'Failure stage not recorded.'
Assert-Check ($failedStatus.lastSuccessUtc -eq $status.lastSuccessUtc) 'Last success lost after failed attempt.'
Assert-Check (@(Get-ChildItem -LiteralPath (Join-Path $root 'archivi/giornalieri') -Directory).Count -eq 1) 'Partial backup published.'
Assert-Check (@(Get-ChildItem -LiteralPath (Join-Path $root '.work') -Directory).Count -eq 0) 'Plaintext left after failure.'
Assert-Rejected { Test-StudioBackupStatus $root $now } 'Failed latest attempt not reported.'
[void](Test-StudioArchive $archive)
$script:checks++

$bad = $config.PSObject.Copy()
$bad.pgBin = Join-Path $TestRoot 'missing-pg'
Assert-Check ((Invoke-StudioBackup $root $bad $credential $now) -eq 1) 'Dump failure accepted.'
Assert-Check ((Get-Content -LiteralPath (Join-Path $root 'logs/status.json') -Raw | ConvertFrom-Json).stage -eq 'dump') 'Dump failure not recorded.'
Assert-Check (@(Get-ChildItem -LiteralPath (Join-Path $root '.work') -Directory).Count -eq 0) 'Plaintext left after dump failure.'

$cipher = Join-Path $archive 'backup.dump.age'
$bytes = [IO.File]::ReadAllBytes($cipher)
$damaged = [byte[]]$bytes.Clone()
$damaged[$damaged.Length - 1] = $damaged[$damaged.Length - 1] -bxor 1
[IO.File]::WriteAllBytes($cipher, $damaged)
Assert-Rejected { Test-StudioArchive $archive } 'Damaged ciphertext passed checksum.'
$tamperedManifest = Get-Content -LiteralPath (Join-Path $archive 'manifest.json') -Raw | ConvertFrom-Json
$originalHash = $tamperedManifest.sha256
$tamperedHash = (Get-FileHash -LiteralPath $cipher -Algorithm SHA256).Hash.ToLowerInvariant()
$tamperedManifest.sha256 = $tamperedHash
Write-StudioJson (Join-Path $archive 'manifest.json') $tamperedManifest
[IO.File]::WriteAllText((Join-Path $archive 'backup.dump.age.sha256'), ($tamperedHash + '  backup.dump.age'))
[void](Test-StudioArchive $archive)
Assert-Rejected {
    Invoke-StudioTool $Age @('--decrypt', '--identity', $identity, '--output',
        (Join-Path $TestRoot 'must-fail.dump'), $cipher)
} 'Authenticated decryption accepted tampering even after checksum replacement.'
[IO.File]::WriteAllBytes($cipher, $bytes)
$tamperedManifest.sha256 = $originalHash
Write-StudioJson (Join-Path $archive 'manifest.json') $tamperedManifest
[IO.File]::WriteAllText((Join-Path $archive 'backup.dump.age.sha256'), ($originalHash + '  backup.dump.age'))
Write-StudioStatus $root 'success' 'completato' $now.ToString('o') $status.archive
Assert-Rejected { Test-StudioBackupStatus $root $now.AddHours(25) } 'Stale backup accepted.'

function Copy-TestArchive([string]$Bucket, [datetime]$Created, [string]$Suffix) {
    $name = 'sc-studio-' + $Created.ToUniversalTime().ToString('yyyyMMddTHHmmssZ') + '-' + $Suffix
    $destination = Join-Path (Join-Path $root ('archivi/' + $Bucket)) $name
    [void][IO.Directory]::CreateDirectory($destination)
    foreach ($file in Get-ChildItem -LiteralPath $archive) { [IO.File]::Copy($file.FullName, (Join-Path $destination $file.Name)) }
    $manifest = Get-Content -LiteralPath (Join-Path $destination 'manifest.json') -Raw | ConvertFrom-Json
    $manifest.createdUtc = $Created.ToUniversalTime().ToString('o')
    Write-StudioJson (Join-Path $destination 'manifest.json') $manifest
    return $destination
}
$oldDaily = Copy-TestArchive 'giornalieri' $now.AddDays(-15) 'aaaaaaaa'
$recentDaily = Copy-TestArchive 'giornalieri' $now.AddDays(-13) 'bbbbbbbb'
$oldWeekly = Copy-TestArchive 'settimanali' $now.AddDays(-57) 'cccccccc'
$oldMonthly = Copy-TestArchive 'mensili' $now.AddMonths(-13) 'dddddddd'
$unrelated = Join-Path $root 'archivi/giornalieri/do-not-delete'
[void][IO.Directory]::CreateDirectory($unrelated)
Remove-StudioExpiredArchives $root $now
foreach ($path in @($oldDaily, $oldWeekly, $oldMonthly)) { Assert-Check (-not (Test-Path -LiteralPath $path)) 'Expired owned archive retained.' }
Assert-Check (Test-Path -LiteralPath $recentDaily) 'Recent archive deleted.'
Assert-Check (Test-Path -LiteralPath $unrelated) 'Foreign directory deleted.'
$withExtra = Copy-TestArchive 'giornalieri' $now.AddDays(-20) 'eeeeeeee'
[IO.File]::WriteAllText((Join-Path $withExtra 'foreign.txt'), 'synthetic extra file')
Assert-Rejected { Remove-StudioExpiredArchives $root $now } 'Archive with foreign files deleted.'
Assert-Check (Test-Path -LiteralPath (Join-Path $withExtra 'foreign.txt')) 'Foreign file removed.'
Assert-Check ((Invoke-StudioBackup $root $config $credential $now) -eq 2) 'Retention warning not returned.'
Assert-Check ((Get-Content -LiteralPath (Join-Path $root 'logs/status.json') -Raw | ConvertFrom-Json).state -eq 'warning') 'Retention warning not recorded.'

$foreignTarget = Join-Path $TestRoot 'foreign-target'
[void][IO.Directory]::CreateDirectory($foreignTarget)
$link = Join-Path $TestRoot 'linked-directory'
[void](New-Item -ItemType SymbolicLink -Path $link -Target $foreignTarget)
Assert-Rejected { Assert-StudioPath $link } 'Symlink accepted.'
$invalidWork = Join-Path $root '.work/not-a-generated-directory'
Assert-Rejected { Remove-StudioWorkDirectory $root $invalidWork } 'Broad cleanup accepted.'
$logs = (Get-ChildItem -LiteralPath (Join-Path $root 'logs') -File | Get-Content -Raw) -join ''
Assert-Check (-not $logs.Contains('synthetic-only-not-a-real-password') -and -not $logs.Contains($DatabaseHost) -and
    -not $logs.Contains($DatabaseUser)) 'Sensitive details leaked into logs.'
Write-Host ('PASS: ' + $script:checks + ' assertions; real dump/encryption/decryption/restore and failure paths verified.')
