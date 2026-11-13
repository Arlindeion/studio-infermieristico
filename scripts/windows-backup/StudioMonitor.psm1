Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'StudioBackup.psm1') -Force

function Send-StudioBackupSignal {
    param([string]$Root)
    $path = Join-Path $Root 'config/monitor.credential.xml'
    if (-not (Test-Path -LiteralPath $path)) { return }
    $response = $null; $reader = $null
    try {
        Assert-StudioWindows
        Assert-StudioPath $path
        Assert-StudioPrivateAcl $path
        Test-StudioBackupStatus $Root
        $credential = Import-Clixml -LiteralPath $path
        if ($credential -isnot [Management.Automation.PSCredential]) { throw 'Formato monitor non valido.' }
        $endpoint = $credential.GetNetworkCredential().Password
        if ($endpoint -cnotmatch '^https://hc-ping\.com/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$') { throw 'Destinazione monitor non valida.' }
        $request = [Net.HttpWebRequest]::Create($endpoint)
        $request.Method = 'POST'; $request.ContentLength = 0
        $request.Timeout = 8000; $request.ReadWriteTimeout = 8000
        $request.AllowAutoRedirect = $false; $request.UseDefaultCredentials = $false
        $response = $request.GetResponse()
        $reader = New-Object IO.StreamReader($response.GetResponseStream())
        $buffer = New-Object char[] 128
        $count = $reader.Read($buffer, 0, 128)
        $reply = [string]::new($buffer, 0, $count).Trim()
        if ([int]$response.StatusCode -ne 200 -or $reply -cne 'OK') { throw 'Segnale non confermato.' }
        Write-StudioJson (Join-Path $Root 'logs/monitor.json') @{ state = 'success'; attemptedUtc = [datetime]::UtcNow.ToString('o') }
    } catch {
        # Never include endpoint, native errors or backup data in logs.
        try { Write-StudioJson (Join-Path $Root 'logs/monitor.json') @{ state = 'error'; attemptedUtc = [datetime]::UtcNow.ToString('o') } } catch { }
    } finally {
        if ($reader) { $reader.Dispose() }
        if ($response) { $response.Dispose() }
    }
}

Export-ModuleMember -Function Send-StudioBackupSignal
