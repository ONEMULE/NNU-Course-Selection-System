param(
    [string]$ProjectPath = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
)

$base = Join-Path $ProjectPath '选课'
$repoRoot = Join-Path $base '03_仓库源码'
$logPath = Join-Path $base '02_公开资料/repository_index/repository_collection_log.csv'
$outPath = Join-Path $base '04_提取分析/repository_fingerprint_matrix.csv'
$patterns = [ordered]@{
    xsxkapp='xsxkapp'
    volunteer_do='volunteer\.do'
    vcode_do='student/4/vcode\.do'
    recommendedCourse_do='recommendedCourse\.do'
    publicCourse_do='publicCourse\.do'
    programCourse_do='programCourse\.do'
    xkxf_do='xkxf\.do'
    nnu_domain='nnu\.edu\.cn'
    njnu_domain='njnu'
    token_cookie='token|cookie|session'
}
$rows = [System.Collections.Generic.List[object]]::new()
$logs = @{}
if (Test-Path -LiteralPath $logPath) { foreach($r in (Import-Csv $logPath)){ $logs[$r.owner_repo]=$r } }

foreach ($category in @('00_nnu_direct','01_same_stack','02_adjacent')) {
    $categoryDir = Join-Path $repoRoot $category
    if (-not (Test-Path -LiteralPath $categoryDir)) { continue }
    foreach ($repo in (Get-ChildItem -LiteralPath $categoryDir -Directory)) {
        $ownerRepo = $repo.Name -replace '__','/'
        $fileCount = (Get-ChildItem -LiteralPath $repo.FullName -Recurse -File | Where-Object { $_.FullName -notmatch '[\\/]\.git[\\/]' } | Measure-Object).Count
        $values = [ordered]@{owner_repo=$ownerRepo;category=$category;commit='';file_count=$fileCount}
        if ($logs.ContainsKey($ownerRepo)) { $values.commit=$logs[$ownerRepo].commit }
        foreach ($name in $patterns.Keys) {
            $count = 0
            $matches = & rg -i -l --hidden --glob '!.git/**' --glob '!*.lock' -- $patterns[$name] $repo.FullName 2>$null
            if ($LASTEXITCODE -eq 0 -and $matches) { $count = @($matches).Count }
            $values[$name + '_files'] = $count
        }
        $rows.Add([pscustomobject]$values)
    }
}
$outDir = Split-Path -Parent $outPath
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$rows | Sort-Object category,owner_repo | Export-Csv -LiteralPath $outPath -NoTypeInformation -Encoding UTF8
Write-Output "Scanned $($rows.Count) repositories; matrix: $outPath"
