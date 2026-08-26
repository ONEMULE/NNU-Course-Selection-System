param(
    [string]$BasePath = (Join-Path (Split-Path -Parent $PSScriptRoot) '01_本地证据')
)

$rawPath = Join-Path $BasePath 'raw'
$sanitizedPath = Join-Path $BasePath 'sanitized'
if (-not (Test-Path -LiteralPath $rawPath)) { throw "Raw evidence directory not found: $rawPath" }

Get-ChildItem -LiteralPath $rawPath -Recurse -File -Filter '*.html' | ForEach-Object {
    $relative = $_.FullName.Substring($rawPath.Length).TrimStart('\','/')
    $destination = Join-Path $sanitizedPath $relative
    $destinationDir = Split-Path -Parent $destination
    New-Item -ItemType Directory -Force -Path $destinationDir | Out-Null

    $text = [System.IO.File]::ReadAllText($_.FullName, [System.Text.Encoding]::UTF8)
    # Redact query/form values that can carry a live session or account identifier.
    $text = [regex]::Replace($text, '(?i)([?&]token=)[^&#"''\s<>]+', '$1[REDACTED_TOKEN]')
    $text = [regex]::Replace($text, '(?i)((?:["'']token["'']\s*[:=]\s*["'']))[^"'']+', '$1[REDACTED_TOKEN]')
    $text = [regex]::Replace($text, '(?i)((?:["''](?:studentCode|studentcode|xh|uid|number|studentId)["'']\s*[:=]\s*["'']))[^"'']+', '$1[REDACTED_IDENTIFIER]')

    [System.IO.File]::WriteAllText($destination, $text, [System.Text.UTF8Encoding]::new($false))
}

Write-Output "Sanitized HTML snapshots written to $sanitizedPath"
