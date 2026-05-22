# validate-streams.ps1
# Pure PowerShell stream validator for playlist.m3u
# Usage: .\validate-streams.ps1 [playlist.m3u]
# Output: stream-validation-log.txt + failed-streams.txt + passed-streams.txt

param(
    [string]$Playlist = "playlist.m3u"
)

$LogFile    = "stream-validation-log.txt"
$FailedFile = "failed-streams.txt"
$PassedFile = "passed-streams.txt"
$TimeoutSec = 15

if (-not (Test-Path $Playlist)) {
    Write-Host "[ERROR] Playlist not found: $Playlist"
    exit 1
}

Write-Host "Reading: $Playlist"
$content = Get-Content $Playlist -Raw
$lines   = $content -split "`n"

$channels = @()
$i = 0
while ($i -lt $lines.Count) {
    $line = $lines[$i].Trim()
    if ($line.StartsWith("#EXTINF:")) {
        $j = $i + 1
        while ($j -lt $lines.Count -and ($lines[$j].Trim() -eq "" -or $lines[$j].Trim().StartsWith("#"))) { $j++ }
        $url = if ($j -lt $lines.Count) { $lines[$j].Trim() } else { "" }
        if ($url -match "^https?://") {
            $attrs   = $line.Substring(8)
            $commaAt = $attrs.LastIndexOf(",")
            $name    = if ($commaAt -ge 0) { $attrs.Substring($commaAt + 1).Trim() } else { "" }
            $tvgId   = if ($attrs -match 'tvg-id="([^"]+)"') { $Matches[1] } else { "" }
            $logo    = if ($attrs -match 'tvg-logo="([^"]+)"') { $Matches[1] } else { "" }
            $grp     = if ($attrs -match 'group-title="([^"]+)"') { $Matches[1] } else { "" }
            $channels += [PSCustomObject]@{
                Name    = $name
                ID      = $tvgId
                Logo    = $logo
                Group   = $grp
                URL     = $url
                ExtInf  = $line
            }
            $i = $j
        } else {
            $i++
        }
    } else {
        $i++
    }
}

$total     = $channels.Count
$passed    = 0
$failed    = 0
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

$sep = "================================================================================"
"" | Out-File -FilePath $LogFile -Encoding UTF8
"$sep" | Out-File -FilePath $LogFile -Append -Encoding UTF8
"STREAM VALIDATION LOG - $timestamp" | Out-File -FilePath $LogFile -Append -Encoding UTF8
"Playlist: $Playlist" | Out-File -FilePath $LogFile -Append -Encoding UTF8
"Total channels: $total" | Out-File -FilePath $LogFile -Append -Encoding UTF8
"$sep" | Out-File -FilePath $LogFile -Append -Encoding UTF8
"" | Out-File -FilePath $LogFile -Append -Encoding UTF8

"" | Out-File -FilePath $FailedFile -Encoding UTF8
"# Failed streams - $timestamp" | Out-File -FilePath $FailedFile -Append -Encoding UTF8
"# Format: tvg-id|name|group|url|HTTP_code|reason" | Out-File -FilePath $FailedFile -Append -Encoding UTF8

"" | Out-File -FilePath $PassedFile -Encoding UTF8
"# Passed streams - $timestamp" | Out-File -FilePath $PassedFile -Append -Encoding UTF8
"# Format: tvg-id|name|url|HTTP_code|content_type" | Out-File -FilePath $PassedFile -Append -Encoding UTF8

Write-Host "Found $total channels. Starting validation..."
Write-Host "Log: $LogFile"
Write-Host ""

$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

for ($idx = 0; $idx -lt $channels.Count; $idx++) {
    $ch  = $channels[$idx]
    $pct = ($idx + 1) / $total * 100
    $elapsed = $stopwatch.Elapsed.ToString("mm\:ss")
    $namePad = $ch.Name.PadRight(40)
    if ($namePad.Length -gt 40) { $namePad = $namePad.Substring(0, 40) }
    Write-Host -NoNewline "`r[$($idx+1)/$total ($($pct.ToString('0.0'))%) $elapsed] $namePad"

    $ok = $false; $httpCode = 0; $ctype = ""; $reason = ""

    try {
        $resp = Invoke-WebRequest -Uri $ch.URL -Method Head -MaximumRedirection 5 `
            -TimeoutSec $TimeoutSec -UseBasicParsing 2>$null
        $httpCode = [int]$resp.StatusCode
        $ctype    = $resp.Headers["Content-Type"]
        if ($httpCode -eq 200 -and ($ctype -match "mpegurl|m3u8|apple|octet")) {
            $ok = $true; $reason = "ok"
        } elseif ($httpCode -ge 200 -and $httpCode -lt 300) {
            $ok = $true; $reason = "ok"
        } elseif ($httpCode -eq 404) {
            $ok = $false; $reason = "404 Not Found"
        } elseif ($httpCode -eq 403) {
            $ok = $false; $reason = "403 Forbidden"
        } else {
            $ok = $false; $reason = "HTTP $httpCode"
        }
    } catch {
        $errMsg = $_.Exception.Message
        if ($errMsg -match "404")      { $httpCode = 404; $reason = "404 Not Found"; $ok = $false }
        elseif ($errMsg -match "403")  { $httpCode = 403; $reason = "403 Forbidden"; $ok = $false }
        elseif ($errMsg -match "timeout|Timeout") { $httpCode = 0; $reason = "timeout"; $ok = $false }
        else {
            $msg = $errMsg.Substring(0, [Math]::Min(80, $errMsg.Length))
            $httpCode = 0; $reason = $msg; $ok = $false
        }
    }

    $statusStr = if ($ok) { "PASS" } else { "FAIL" }

    $logEntry = "[$statusStr] " + $ch.ID + "`n"
    $logEntry = $logEntry + "  Name:   " + $ch.Name + "`n"
    $logEntry = $logEntry + "  Group:  " + $ch.Group + "`n"
    $logEntry = $logEntry + "  URL:    " + $ch.URL + "`n"
    $logEntry = $logEntry + "  Result: HTTP $httpCode | $ctype | $reason`n`n"
    $logEntry | Out-File -FilePath $LogFile -Append -Encoding UTF8

    if ($ok) {
        $passed++
        $line = $ch.ID + "|" + $ch.Name + "|" + $ch.URL + "|" + $httpCode + "|" + $ctype
        $line | Out-File -FilePath $PassedFile -Append -Encoding UTF8
    } else {
        $failed++
        $line = $ch.ID + "|" + $ch.Name + "|" + $ch.Group + "|" + $ch.URL + "|" + $httpCode + "|" + $reason
        $line | Out-File -FilePath $FailedFile -Append -Encoding UTF8
    }
}

$stopwatch.Stop()
Write-Host ""
Write-Host ""
Write-Host "Results: $passed passed, $failed failed ($($stopwatch.Elapsed.ToString('mm\:ss')) elapsed)"
Write-Host "Full log:   $LogFile"
Write-Host "Failed:     $FailedFile ($failed entries)"
Write-Host "Passed:     $PassedFile ($passed entries)"
Write-Host ""
Write-Host "Send failed-streams.txt to Vectrix for analysis."
