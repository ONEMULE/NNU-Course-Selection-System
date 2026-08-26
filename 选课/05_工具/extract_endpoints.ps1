param(
    [string]$EvidencePath = (Join-Path (Split-Path -Parent $PSScriptRoot) '01_本地证据/sanitized'),
    [string]$OutputPath = (Join-Path (Split-Path -Parent $PSScriptRoot) '04_提取分析/endpoint_inventory.csv')
)

if (-not (Test-Path -LiteralPath $EvidencePath)) { throw "Evidence directory not found: $EvidencePath" }
$rows = [System.Collections.Generic.List[object]]::new()
$seen = @{}
$files = Get-ChildItem -LiteralPath $EvidencePath -Recurse -File | Where-Object { $_.Extension -in @('.js','.html') }

foreach ($file in $files) {
    $text = [System.IO.File]::ReadAllText($file.FullName, [System.Text.Encoding]::UTF8)
    $relative = $file.FullName.Substring($EvidencePath.Length).TrimStart('\','/')

    # Relative strings used by the front end, e.g. /sys/xsxkapp/elective/volunteer.do.
    foreach ($m in [regex]::Matches($text, '(?i)["'']([^"'']*(?:xsxkapp|student|elective|publicinfo|util|vcode|xkxf|batch|volunteer|course|logout|login|capacity|result)[^"'']*\.do(?:\?[^"'']*)?)["'']')) {
        $rawPath = $m.Groups[1].Value
        if ($rawPath -notmatch '(?i)\.do') { continue }
        $queryKeys = ''
        if ($rawPath.Contains('?')) {
            $query = $rawPath.Substring($rawPath.IndexOf('?') + 1)
            $queryKeys = (($query -split '&' | ForEach-Object { ($_ -split '=')[0] } | Where-Object { $_ }) -join ';')
        }
        $path = $rawPath.Split('?')[0]
        $key = ($path + '|' + $queryKeys).ToLowerInvariant()
        if (-not $seen.ContainsKey($key)) {
            $seen[$key] = $true
            $rows.Add([pscustomobject]@{endpoint=$path;query_keys=$queryKeys;source_file=$relative;kind='front_end_string';evidence='local_snapshot'})
        }
    }

    # Absolute URLs are retained only as origin + path; query values are excluded.
    foreach ($m in [regex]::Matches($text, '(?i)https?://[^"''<>\s]+')) {
        try {
            $uri = [Uri]$m.Value.TrimEnd(')', ',', ';')
            if ($uri.AbsolutePath -match '(?i)(xsxkapp|ehall|authserver)' -and $uri.AbsolutePath -match '(?i)\.do|xsxkapp') {
                $path = $uri.GetLeftPart([System.UriPartial]::Path)
                $key = $path.ToLowerInvariant()
                if (-not $seen.ContainsKey($key)) {
                    $seen[$key] = $true
                    $rows.Add([pscustomobject]@{endpoint=$path;query_keys='';source_file=$relative;kind='absolute_url';evidence='local_snapshot'})
                }
            }
        } catch { }
    }
}

$outDir = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$rows | Sort-Object endpoint,source_file | Export-Csv -LiteralPath $OutputPath -NoTypeInformation -Encoding UTF8
Write-Output "Extracted $($rows.Count) unique endpoint candidates to $OutputPath"
