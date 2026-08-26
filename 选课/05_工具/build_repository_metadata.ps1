param(
    [string]$ProjectPath = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
)

$base = Join-Path $ProjectPath '选课'
$repoRoot = Join-Path $base '03_仓库源码'
$outPath = Join-Path $base '04_提取分析/repository_metadata.csv'
$rows = [System.Collections.Generic.List[object]]::new()

foreach ($category in @('00_nnu_direct','01_same_stack','02_adjacent')) {
    $categoryDir = Join-Path $repoRoot $category
    if (-not (Test-Path -LiteralPath $categoryDir)) { continue }
    foreach ($repo in (Get-ChildItem -LiteralPath $categoryDir -Directory)) {
        $ownerRepo = $repo.Name -replace '__','/'
        $readme = Get-ChildItem -LiteralPath $repo.FullName -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '(?i)^readme(\..*)?$' } | Select-Object -First 1
        $license = Get-ChildItem -LiteralPath $repo.FullName -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '(?i)^(license|copying)(\..*)?$' } | Select-Object -First 1
        $manifests = Get-ChildItem -LiteralPath $repo.FullName -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
            $_.FullName -notmatch '[\\/]\.git[\\/]' -and $_.Name -in @('requirements.txt','pyproject.toml','package.json','go.mod','Cargo.toml','pom.xml','composer.json','Gemfile')
        } | ForEach-Object { $_.FullName.Substring($repo.FullName.Length).TrimStart('\','/') } | Sort-Object
        $commit = (& git -C $repo.FullName rev-parse HEAD 2>$null).Trim()
        $commitDate = (& git -C $repo.FullName show -s --format=%cI HEAD 2>$null).Trim()
        $origin = (& git -C $repo.FullName remote get-url origin 2>$null).Trim()
        $files = Get-ChildItem -LiteralPath $repo.FullName -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.FullName -notmatch '[\\/]\.git[\\/]' }
        $readmeName = ''
        if ($readme) { $readmeName = $readme.Name }
        $licenseName = ''
        if ($license) { $licenseName = $license.Name }
        $rows.Add([pscustomobject]@{
            owner_repo=$ownerRepo
            category=$category
            origin=$origin
            commit=$commit
            commit_date=$commitDate
            file_count=$files.Count
            source_bytes=($files | Measure-Object Length -Sum).Sum
            readme=$readmeName
            license_file=$licenseName
            manifests=($manifests -join ';')
        })
    }
}
$outDir = Split-Path -Parent $outPath
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$rows | Sort-Object category,owner_repo | Export-Csv -LiteralPath $outPath -NoTypeInformation -Encoding UTF8
Write-Output "Wrote metadata for $($rows.Count) repositories to $outPath"
