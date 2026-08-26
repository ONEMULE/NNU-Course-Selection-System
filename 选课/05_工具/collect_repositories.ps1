param(
    [string]$BasePath = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)),
    [switch]$IncludeP2
)

$projectPath = Join-Path $BasePath '选课'
$manifestPath = Join-Path $projectPath '00_研究索引/仓库采集清单.csv'
$repoRoot = Join-Path $projectPath '03_仓库源码'
$indexRoot = Join-Path $projectPath '02_公开资料/repository_index'
$logPath = Join-Path $indexRoot 'repository_collection_log.csv'

if (-not (Test-Path -LiteralPath $manifestPath)) { throw "Manifest not found: $manifestPath" }
New-Item -ItemType Directory -Force -Path $indexRoot | Out-Null

$records = [System.Collections.Generic.List[object]]::new()
$rows = Import-Csv -LiteralPath $manifestPath
foreach ($row in $rows) {
    if ($row.priority -eq 'P2' -and -not $IncludeP2) { continue }
    $categoryPath = switch ($row.category) {
        'nnu_direct' { '00_nnu_direct' }
        'same_stack' { '01_same_stack' }
        'adjacent' { '02_adjacent' }
        default { '03_unverified_or_failed' }
    }
    $repoName = ($row.owner_repo -replace '/', '__')
    $destination = Join-Path (Join-Path $repoRoot $categoryPath) $repoName
    $status = 'failed'
    $message = ''
    $commit = ''
    $started = Get-Date

    try {
        if (Test-Path -LiteralPath (Join-Path $destination '.git')) {
            # Never reset or overwrite an existing checkout; preserve user changes.
            $status = 'existing'
        } else {
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
            & git clone --depth 1 --no-tags --filter=blob:none -- $row.url $destination 2>&1 | Out-String | Out-Null
            if ($LASTEXITCODE -eq 0) { $status = 'cloned' } else { throw "git clone exit code $LASTEXITCODE" }
        }
        $commit = (& git -C $destination rev-parse HEAD 2>$null).Trim()
    } catch {
        $message = $_.Exception.Message
        if (Test-Path -LiteralPath $destination -and -not (Test-Path -LiteralPath (Join-Path $destination '.git'))) {
            Move-Item -LiteralPath $destination -Destination (Join-Path $projectPath '03_仓库源码/03_unverified_or_failed') -Force -ErrorAction SilentlyContinue
        }
    }

    $records.Add([pscustomobject]@{
        collected_at=(Get-Date -Format 'yyyy-MM-ddTHH:mm:ssK')
        owner_repo=$row.owner_repo
        url=$row.url
        category=$row.category
        status=$status
        commit=$commit
        message=$message
        elapsed_seconds=[math]::Round(((Get-Date)-$started).TotalSeconds,1)
    })
    Write-Output ("{0}: {1}" -f $row.owner_repo,$status)
}

$records | Export-Csv -LiteralPath $logPath -NoTypeInformation -Encoding UTF8
Write-Output "Collection log: $logPath"
