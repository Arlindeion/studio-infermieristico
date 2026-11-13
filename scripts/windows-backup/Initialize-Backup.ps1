#Requires -Version 5.1
param([string]$Root = 'C:\SCStudioBackup', [string]$PgBin = 'C:\Program Files\PostgreSQL\18\bin')
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'StudioBackup.psm1') -Force
Assert-StudioWindows
$Root = Get-StudioRoot $Root
foreach ($relative in @('', 'scripts', 'config', 'recovery', '.work', 'logs', 'archivi', 'archivi/giornalieri', 'archivi/settimanali', 'archivi/mensili')) {
    $path = if ($relative) { Join-Path $Root $relative } else { $Root }
    Set-StudioPrivateDirectory $path
}
if (Test-Path -LiteralPath (Join-Path $Root 'config/settings.json')) {
    throw 'Configurazione gia presente: non viene sovrascritta. Non eliminare le chiavi di recupero.'
}
foreach ($tool in @('pg_dump.exe', 'pg_restore.exe')) {
    [void](Invoke-StudioTool (Join-Path $PgBin $tool) @('--version'))
}
$age = (Get-Command age.exe -CommandType Application -ErrorAction Stop).Source
$keygen = (Get-Command age-keygen.exe -CommandType Application -ErrorAction Stop).Source
$identity = Join-Path $Root 'recovery/recovery.agekey'
if (-not (Test-Path -LiteralPath $identity)) {
    [void](Invoke-StudioTool $keygen @('--output', $identity))
}
$recipient = (Invoke-StudioTool $keygen @('-y', $identity)).Trim()
if ($recipient -notmatch '^age1[0-9a-z]{58}$') { throw 'Chiave pubblica non valida.' }
Write-Host 'La chiave PRIVATA di recupero si trova nella cartella recovery.'
Write-Host 'Conservarne una copia separata e protetta: non inviarla in chat e non inserirla nei backup.'
if ((Read-Host 'Hai salvato la chiave anche separatamente? Digita CONFERMO') -cne 'CONFERMO') {
    throw 'Configurazione fermata. Nessuna connessione al database eseguita.'
}
$dbHost = (Read-Host 'Host ESTERNO del database Render (solo nome host, non URL completo)').Trim()
$database = (Read-Host 'Nome del database').Trim()
$user = (Read-Host 'Utente database dedicato al backup').Trim()
if ($dbHost -notmatch '^[a-zA-Z0-9.-]+\.render\.com$' -or $database -notmatch '^[a-zA-Z0-9_-]+$' -or
    $user -notmatch '^[a-zA-Z0-9_-]+$') { throw 'Dati non validi. Non incollare URL o password nei campi testuali.' }
$password = Read-Host 'Password database (nascosta)' -AsSecureString
if ($password.Length -eq 0) { throw 'Password mancante: configurazione non salvata.' }
$credential = New-Object Management.Automation.PSCredential($user, $password)
$credential | Export-Clixml -LiteralPath (Join-Path $Root 'config/database.credential.xml')
$password.Dispose()
Save-StudioTrustBundle (Join-Path $Root 'config/roots.pem')
Write-StudioJson (Join-Path $Root 'config/settings.json') ([ordered]@{
    schemaVersion = 1; ownerSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    host = $dbHost; port = 5432; database = $database; pgBin = $PgBin; age = $age; recipient = $recipient
})
try {
    if (-not [Diagnostics.EventLog]::SourceExists('SCStudioBackup')) {
        [Diagnostics.EventLog]::CreateEventSource('SCStudioBackup', 'Application')
    }
} catch { Write-Warning 'Sorgente eventi non registrata: lo stato rimane disponibile nella cartella logs.' }
Write-Host 'Configurazione locale salvata. Nessun backup o accesso a Render ancora eseguito.'
Write-Host 'Usare lo stesso account Windows per il backup e per la futura attivita pianificata.'
