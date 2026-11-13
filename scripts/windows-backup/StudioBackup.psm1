Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-StudioWindows {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'Questo comando richiede Windows.' }
}

function Assert-StudioPath {
    param([Parameter(Mandatory)][string]$Path)
    $cursor = [IO.Path]::GetFullPath($Path)
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            if ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw 'Percorso rifiutato: collegamento simbolico o junction.'
            }
        }
        $parent = [IO.Path]::GetDirectoryName($cursor)
        if ($parent -eq $cursor) { break }
        $cursor = $parent
    }
}

function Get-StudioRoot {
    param([string]$Root)
    if (-not [IO.Path]::IsPathRooted($Root) -or $Root.StartsWith('\\')) {
        throw 'Usare un percorso assoluto su disco locale.'
    }
    $full = [IO.Path]::GetFullPath($Root).TrimEnd([char[]]'\/')
    if ([IO.Path]::GetFileName($full) -ne 'SCStudioBackup') {
        throw 'La cartella deve chiamarsi SCStudioBackup; non usare la radice del disco.'
    }
    Assert-StudioPath $full
    return $full
}

function Set-StudioPrivateDirectory {
    param([string]$Path)
    Assert-StudioWindows
    Assert-StudioPath $Path
    [void][IO.Directory]::CreateDirectory($Path)
    $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User
    $acl = New-Object Security.AccessControl.DirectorySecurity
    $acl.SetOwner($sid)
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($identity in @($sid.Value, 'S-1-5-18', 'S-1-5-32-544')) {
        $rule = New-Object Security.AccessControl.FileSystemAccessRule(
            (New-Object Security.Principal.SecurityIdentifier($identity)),
            'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
        $acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $Path -AclObject $acl
}

function Assert-StudioPrivateAcl {
    param([string]$Path)
    Assert-StudioWindows
    $allowed = @([Security.Principal.WindowsIdentity]::GetCurrent().User.Value, 'S-1-5-18', 'S-1-5-32-544')
    foreach ($rule in (Get-Acl -LiteralPath $Path).Access) {
        $sid = $rule.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value
        if ($rule.AccessControlType -eq 'Allow' -and $sid -notin $allowed) {
            throw 'Permessi troppo ampi sulla cartella backup o sulla configurazione.'
        }
    }
}

function Write-StudioJson {
    param([string]$Path, $Value)
    Assert-StudioPath $Path
    $temporary = $Path + '.' + [guid]::NewGuid().ToString('N') + '.tmp'
    try {
        [IO.File]::WriteAllText($temporary, ($Value | ConvertTo-Json -Depth 5), (New-Object Text.UTF8Encoding($false)))
        if ([IO.File]::Exists($Path)) { [IO.File]::Replace($temporary, $Path, [Management.Automation.Language.NullString]::Value) }
        else { [IO.File]::Move($temporary, $Path) }
    } finally {
        if ([IO.File]::Exists($temporary)) { [IO.File]::Delete($temporary) }
    }
}

function Save-StudioTrustBundle {
    param([string]$Path)
    Assert-StudioWindows
    Assert-StudioPath $Path
    $certificates = New-Object Text.StringBuilder
    foreach ($location in @([Security.Cryptography.X509Certificates.StoreLocation]::LocalMachine,
                            [Security.Cryptography.X509Certificates.StoreLocation]::CurrentUser)) {
        $store = New-Object Security.Cryptography.X509Certificates.X509Store('Root', $location)
        try {
            $store.Open([Security.Cryptography.X509Certificates.OpenFlags]::ReadOnly)
            foreach ($certificate in $store.Certificates) {
                [void]$certificates.AppendLine('-----BEGIN CERTIFICATE-----')
                [void]$certificates.AppendLine([Convert]::ToBase64String($certificate.RawData, [Base64FormattingOptions]::InsertLineBreaks))
                [void]$certificates.AppendLine('-----END CERTIFICATE-----')
            }
        } finally { $store.Close() }
    }
    if ($certificates.Length -eq 0) { throw 'Nessuna autorita attendibile disponibile in Windows.' }
    # Export public trust anchors only, never certificates' private keys.
    [IO.File]::WriteAllText($Path, $certificates.ToString(), [Text.Encoding]::ASCII)
}

function Invoke-StudioTool {
    param([string]$Executable, [string[]]$Arguments, [hashtable]$Environment = @{}, [ValidateRange(1,3600)][int]$TimeoutSeconds = 900)
    if (-not [IO.File]::Exists($Executable)) { throw 'Strumento richiesto non trovato.' }
    $info = New-Object Diagnostics.ProcessStartInfo
    $info.FileName = $Executable
    # Arguments are flags and file paths, never connection strings/passwords.
    $info.Arguments = (($Arguments | ForEach-Object { '"' + $_.Replace('"', '\"') + '"' }) -join ' ')
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    foreach ($key in @($info.EnvironmentVariables.Keys)) {
        if ($key -like 'PG*' -or $key -eq 'DATABASE_URL') { $info.EnvironmentVariables.Remove($key) }
    }
    foreach ($key in $Environment.Keys) { $info.EnvironmentVariables[$key] = [string]$Environment[$key] }
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $info
    try {
        [void]$process.Start()
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            $process.Kill()
            $process.WaitForExit()
            throw 'Tempo massimo dello strumento superato.'
        }
        $process.WaitForExit()
        $out = $stdout.GetAwaiter().GetResult()
        [void]$stderr.GetAwaiter().GetResult()
        if ($process.ExitCode -ne 0) { throw 'Lo strumento ha restituito un errore. Nessun dettaglio sensibile registrato.' }
        return $out
    } finally {
        foreach ($key in @($info.EnvironmentVariables.Keys)) {
            if ($key -like 'PG*') { $info.EnvironmentVariables.Remove($key) }
        }
        $process.Dispose()
    }
}

function Get-StudioConfiguration {
    param([string]$Root)
    Assert-StudioWindows
    $Root = Get-StudioRoot $Root
    foreach ($relative in @('', 'config', 'config/settings.json', 'config/database.credential.xml', 'config/roots.pem', 'archivi', '.work', 'logs')) {
        $path = if ($relative) { Join-Path $Root $relative } else { $Root }
        Assert-StudioPath $path
        Assert-StudioPrivateAcl $path
    }
    $config = Get-Content -LiteralPath (Join-Path $Root 'config/settings.json') -Encoding UTF8 -Raw | ConvertFrom-Json
    if ($config.schemaVersion -ne 1 -or $config.ownerSid -ne [Security.Principal.WindowsIdentity]::GetCurrent().User.Value) {
        throw 'Configurazione non valida per questo utente.'
    }
    if ($config.host -notmatch '^[a-zA-Z0-9.-]+\.render\.com$' -or
        $config.database -notmatch '^[a-zA-Z0-9_-]+$' -or
        $config.recipient -notmatch '^age1[0-9a-z]{58}$' -or
        $config.port -lt 1 -or $config.port -gt 65535) {
        throw 'Configurazione non valida. Nessuna connessione eseguita.'
    }
    return $config
}

function New-StudioWorkDirectory {
    param([string]$Root)
    $base = Join-Path $Root '.work'
    Assert-StudioPath $base
    $path = Join-Path $base ([guid]::NewGuid().ToString('N'))
    [void][IO.Directory]::CreateDirectory($path)
    return $path
}

function Remove-StudioWorkDirectory {
    param([string]$Root, [string]$Path)
    if ([IO.Path]::GetDirectoryName($Path) -ne (Join-Path $Root '.work') -or
        [IO.Path]::GetFileName($Path) -notmatch '^[a-f0-9]{32}$') {
        throw 'Pulizia temporanei rifiutata.'
    }
    Assert-StudioPath $Path
    foreach ($item in Get-ChildItem -LiteralPath $Path -Recurse -Force) { Assert-StudioPath $item.FullName }
    Remove-Item -LiteralPath $Path -Recurse -Force
}

function Test-StudioArchive {
    param([string]$Directory)
    Assert-StudioPath $Directory
    $expected = @('backup.dump.age', 'backup.dump.age.sha256', 'manifest.json')
    $files = @(Get-ChildItem -LiteralPath $Directory -Force)
    if ($files.Count -ne 3 -or @($files | Where-Object { $_.PSIsContainer -or $_.Name -notin $expected }).Count) {
        throw 'Archivio incompleto o con file inattesi.'
    }
    foreach ($file in $files) { Assert-StudioPath $file.FullName }
    $manifest = Get-Content -LiteralPath (Join-Path $Directory 'manifest.json') -Encoding UTF8 -Raw | ConvertFrom-Json
    $archive = Join-Path $Directory 'backup.dump.age'
    $hash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    $checksum = (Get-Content -LiteralPath (Join-Path $Directory 'backup.dump.age.sha256') -Raw).Trim()
    if ($manifest.schemaVersion -ne 1 -or $manifest.format -ne 'pg-custom-age-v1' -or
        $manifest.sha256 -cne $hash -or $checksum -cne ($hash + '  backup.dump.age') -or
        (Get-Item -LiteralPath $archive).Length -ne $manifest.bytes -or $manifest.bytes -le 0) {
        throw 'Integrita archivio non valida.'
    }
    return $manifest
}

function ConvertTo-StudioUtc {
    param($Value)
    if ($Value -is [datetime]) { return $Value.ToUniversalTime() }
    return [datetime]::Parse([string]$Value, [Globalization.CultureInfo]::InvariantCulture,
        [Globalization.DateTimeStyles]::RoundtripKind).ToUniversalTime()
}

function Remove-StudioExpiredArchives {
    param([string]$Root, [datetime]$NowUtc)
    $cutoffs = @{ giornalieri = $NowUtc.AddDays(-14); settimanali = $NowUtc.AddDays(-56); mensili = $NowUtc.AddMonths(-12) }
    foreach ($bucket in $cutoffs.Keys) {
        $base = Join-Path (Join-Path $Root 'archivi') $bucket
        Assert-StudioPath $base
        foreach ($directory in Get-ChildItem -LiteralPath $base -Directory -Force) {
            if ($directory.Name -notmatch '^sc-studio-(\d{8}T\d{6}Z)-[a-f0-9]{8}$') { continue }
            $created = [datetime]::ParseExact($Matches[1], 'yyyyMMddTHHmmssZ', [Globalization.CultureInfo]::InvariantCulture,
                [Globalization.DateTimeStyles]::AssumeUniversal -bor [Globalization.DateTimeStyles]::AdjustToUniversal)
            if ($created -ge $cutoffs[$bucket]) { continue }
            $manifest = Test-StudioArchive $directory.FullName
            $manifestDate = ConvertTo-StudioUtc $manifest.createdUtc
            if ($manifestDate.ToString('yyyyMMddTHHmmssZ') -ne $created.ToString('yyyyMMddTHHmmssZ')) {
                throw 'Data archivio incoerente: nessuna eliminazione per questo archivio.'
            }
            foreach ($name in @('backup.dump.age', 'backup.dump.age.sha256', 'manifest.json')) {
                [IO.File]::Delete((Join-Path $directory.FullName $name))
            }
            [IO.Directory]::Delete($directory.FullName, $false)
        }
    }
}

function Write-StudioStatus {
    param([string]$Root, [string]$State, [string]$Stage, [string]$LastSuccessUtc = '', [string]$Archive = '')
    $path = Join-Path $Root 'logs/status.json'
    if ([IO.File]::Exists($path) -and -not $LastSuccessUtc) {
        try {
            $old = Get-Content -LiteralPath $path -Encoding UTF8 -Raw | ConvertFrom-Json
            if ($old.lastSuccessUtc) { $LastSuccessUtc = (ConvertTo-StudioUtc $old.lastSuccessUtc).ToString('o') }
            $Archive = [string]$old.archive
        } catch { $LastSuccessUtc = ''; $Archive = '' }
    }
    $now = [datetime]::UtcNow
    Write-StudioJson $path ([ordered]@{
        schemaVersion = 1; state = $State; stage = $Stage; attemptedUtc = $now.ToString('o')
        lastSuccessUtc = $LastSuccessUtc; archive = $Archive
    })
    $message = '{0} state={1} stage={2}' -f $now.ToString('o'), $State, $Stage
    Add-Content -LiteralPath (Join-Path $Root ('logs/backup-' + $now.ToString('yyyyMMdd') + '.log')) -Value $message
    if ($env:OS -eq 'Windows_NT') {
        try {
            $kind = if ($State -eq 'success') { [Diagnostics.EventLogEntryType]::Information } else { [Diagnostics.EventLogEntryType]::Error }
            [Diagnostics.EventLog]::WriteEntry('SCStudioBackup', $message, $kind, 100)
        } catch { } # The status file remains authoritative if the event source is unavailable.
    }
}

function Invoke-StudioBackup {
    param([string]$Root, $Configuration, [Management.Automation.PSCredential]$Credential, [datetime]$NowUtc = [datetime]::UtcNow)
    $Root = Get-StudioRoot $Root
    foreach ($relative in @('.work', 'logs', 'archivi/giornalieri', 'archivi/settimanali', 'archivi/mensili')) {
        $path = Join-Path $Root $relative
        Assert-StudioPath $path
        [void][IO.Directory]::CreateDirectory($path)
    }
    $lock = $null; $work = $null; $stage = 'lock'
    try {
        Assert-StudioPath (Join-Path $Root '.work/backup.lock')
        $lock = [IO.File]::Open((Join-Path $Root '.work/backup.lock'), [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    } catch { return 3 }
    try {
        $stage = 'spazio'
        $drive = New-Object IO.DriveInfo([IO.Path]::GetPathRoot($Root))
        if ($drive.AvailableFreeSpace -lt 1GB) { throw 'Spazio insufficiente.' }
        $work = New-StudioWorkDirectory $Root
        $raw = Join-Path $work 'database.dump'
        $publish = Join-Path $work 'publish'
        [void][IO.Directory]::CreateDirectory($publish)
        $stage = 'dump'
        $environment = @{
            PGHOST = [string]$Configuration.host; PGPORT = [string]$Configuration.port
            PGDATABASE = [string]$Configuration.database; PGUSER = $Credential.UserName
            PGPASSWORD = $Credential.GetNetworkCredential().Password
            PGSSLMODE = 'verify-full'; PGSSLROOTCERT = (Join-Path $Root 'config/roots.pem'); PGCONNECT_TIMEOUT = '15'
            PGOPTIONS = '-c default_transaction_read_only=on -c statement_timeout=900000'
        }
        try {
            $dump = Join-Path $Configuration.pgBin 'pg_dump.exe'
            $restore = Join-Path $Configuration.pgBin 'pg_restore.exe'
            [void](Invoke-StudioTool $dump @('--no-password', '--format=custom', '--compress=9', '--no-owner', '--no-acl', '--file', $raw) $environment)
        } finally { $environment.Clear() }
        $stage = 'verifica_dump'
        if ((Get-Item -LiteralPath $raw).Length -le 0) { throw 'Dump vuoto.' }
        [void](Invoke-StudioTool $restore @('--list', $raw))
        $stage = 'cifratura'
        $encrypted = Join-Path $publish 'backup.dump.age'
        [void](Invoke-StudioTool $Configuration.age @('--encrypt', '--recipient', $Configuration.recipient, '--output', $encrypted, $raw))
        [IO.File]::Delete($raw)
        $hash = (Get-FileHash -LiteralPath $encrypted -Algorithm SHA256).Hash.ToLowerInvariant()
        [IO.File]::WriteAllText((Join-Path $publish 'backup.dump.age.sha256'), ($hash + '  backup.dump.age' + [Environment]::NewLine))
        Write-StudioJson (Join-Path $publish 'manifest.json') ([ordered]@{
            schemaVersion = 1; format = 'pg-custom-age-v1'; createdUtc = $NowUtc.ToUniversalTime().ToString('o')
            bytes = (Get-Item -LiteralPath $encrypted).Length; sha256 = $hash
        })
        [void](Test-StudioArchive $publish)
        $stage = 'pubblicazione'
        $name = 'sc-studio-' + $NowUtc.ToUniversalTime().ToString('yyyyMMddTHHmmssZ') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 8)
        $buckets = @('giornalieri')
        $localDate = $NowUtc.ToLocalTime()
        if ($localDate.DayOfWeek -eq [DayOfWeek]::Sunday) { $buckets += 'settimanali' }
        if ($localDate.Day -eq 1) { $buckets += 'mensili' }
        foreach ($bucket in $buckets) {
            $staged = Join-Path $work $bucket
            [void][IO.Directory]::CreateDirectory($staged)
            foreach ($file in Get-ChildItem -LiteralPath $publish) { [IO.File]::Copy($file.FullName, (Join-Path $staged $file.Name), $false) }
            [void](Test-StudioArchive $staged)
            $destination = Join-Path (Join-Path (Join-Path $Root 'archivi') $bucket) $name
            [IO.Directory]::Move($staged, $destination)
        }
        $archive = 'archivi/giornalieri/' + $name
        $stage = 'conservazione'
        try { Remove-StudioExpiredArchives $Root $NowUtc.ToUniversalTime() }
        catch {
            Write-StudioStatus $Root 'warning' $stage $NowUtc.ToUniversalTime().ToString('o') $archive
            return 2
        }
        Write-StudioStatus $Root 'success' 'completato' $NowUtc.ToUniversalTime().ToString('o') $archive
        return 0
    } catch {
        Write-StudioStatus $Root 'error' $stage
        return 1
    } finally {
        try {
            if ($work -and [IO.Directory]::Exists($work)) { Remove-StudioWorkDirectory $Root $work }
        } finally { if ($lock) { $lock.Dispose() } }
    }
}

function Test-StudioBackupStatus {
    param([string]$Root, [datetime]$NowUtc = [datetime]::UtcNow)
    $Root = Get-StudioRoot $Root
    Assert-StudioPath (Join-Path $Root 'logs/status.json')
    $status = Get-Content -LiteralPath (Join-Path $Root 'logs/status.json') -Encoding UTF8 -Raw | ConvertFrom-Json
    if ($status.state -ne 'success' -or -not $status.lastSuccessUtc) { throw 'Ultimo tentativo non riuscito o backup assente.' }
    $last = ConvertTo-StudioUtc $status.lastSuccessUtc
    if ($last -gt $NowUtc.ToUniversalTime().AddMinutes(5) -or ($NowUtc.ToUniversalTime() - $last).TotalHours -gt 24) {
        throw 'Backup assente da oltre 24 ore o orologio incoerente.'
    }
    if ($status.archive -notmatch '^archivi/giornalieri/sc-studio-\d{8}T\d{6}Z-[a-f0-9]{8}$') { throw 'Percorso archivio non valido.' }
    [void](Test-StudioArchive (Join-Path $Root $status.archive))
}

Export-ModuleMember -Function *-Studio*
