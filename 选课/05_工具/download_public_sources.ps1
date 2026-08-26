param(
    [string]$ProjectPath = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
)

$base = Join-Path $ProjectPath '选课'
$manifest = Join-Path $base '00_研究索引/外部资料采集清单.csv'
$outRoot = Join-Path $base '02_公开资料'
$logRoot = Join-Path $base '02_公开资料/repository_index'
$log = Join-Path $logRoot 'external_collection_log.csv'
New-Item -ItemType Directory -Force -Path (Join-Path $outRoot 'official'),(Join-Path $outRoot 'gist_greasyfork'),$logRoot | Out-Null

$results = [System.Collections.Generic.List[object]]::new()
$ua = 'Mozilla/5.0 (research archive; offline analysis)'
foreach ($row in (Import-Csv -LiteralPath $manifest)) {
    $started = Get-Date
    $status = if ($row.enabled -eq 'yes') { 'failed' } else { 'skipped_by_policy' }
    $message = ''
    $outFile = ''
    if ($row.enabled -eq 'yes') {
        $group = if ($row.category -eq 'official_pdf') { 'official' } else { 'gist_greasyfork' }
        $outFile = Join-Path (Join-Path $outRoot $group) $row.local_filename
        try {
            if (Test-Path -LiteralPath $outFile) {
                $status = 'exists'
            } else {
                Invoke-WebRequest -Uri $row.download_url -OutFile $outFile -UserAgent $ua -MaximumRedirection 5 -TimeoutSec 45
                $status = if (Test-Path -LiteralPath $outFile) { 'downloaded' } else { 'failed' }
            }
        } catch {
            $message = $_.Exception.Message
            if (Test-Path -LiteralPath $outFile) { Remove-Item -LiteralPath $outFile -Force -ErrorAction SilentlyContinue }
        }
    }
    $hash = ''
    if ($outFile -and (Test-Path -LiteralPath $outFile)) { $hash = (Get-FileHash -LiteralPath $outFile -Algorithm SHA256).Hash }
    $relativeOut = ''
    if ($outFile) { $relativeOut = $outFile.Substring($base.Length).TrimStart('\','/') }
    $results.Add([pscustomobject]@{
        collected_at=(Get-Date -Format 'yyyy-MM-ddTHH:mm:ssK')
        id=$row.id
        source_url=$row.source_url
        download_url=$row.download_url
        local_path=$relativeOut
        status=$status
        sha256=$hash
        message=$message
        elapsed_seconds=[math]::Round(((Get-Date)-$started).TotalSeconds,1)
    })
    Write-Output ("{0}: {1}" -f $row.id,$status)
}
$results | Export-Csv -LiteralPath $log -NoTypeInformation -Encoding UTF8
Write-Output "Collection log: $log"
