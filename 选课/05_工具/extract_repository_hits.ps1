param(
    [string]$ProjectPath = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
)

$base = Join-Path $ProjectPath '选课'
$repoRoot = Join-Path $base '03_仓库源码'
$outPath = Join-Path $base '04_提取分析/repository_endpoint_hits.csv'
$signatures = [ordered]@{
    xsxkapp='xsxkapp'
    volunteer_do='volunteer\.do'
    vcode_do='student/4/vcode\.do'
    recommendedCourse_do='recommendedCourse\.do'
    publicCourse_do='publicCourse\.do'
    programCourse_do='programCourse\.do'
    courseResult_do='courseResult\.do'
    studentstatus_do='studentstatus\.do'
    xkxf_do='xkxf\.do'
    nnu_domain='nnu\.edu\.cn'
    njnu_domain='njnu'
}
$rows = [System.Collections.Generic.List[object]]::new()
foreach ($category in @('00_nnu_direct','01_same_stack','02_adjacent')) {
    $categoryDir = Join-Path $repoRoot $category
    if (-not (Test-Path -LiteralPath $categoryDir)) { continue }
    foreach ($repo in (Get-ChildItem -LiteralPath $categoryDir -Directory)) {
        $ownerRepo = $repo.Name -replace '__','/'
        $files = Get-ChildItem -LiteralPath $repo.FullName -Recurse -File | Where-Object {
            $_.FullName -notmatch '[\\/]\.git[\\/]' -and $_.Extension -notin @('.png','.jpg','.jpeg','.gif','.ico','.pdf','.zip','.7z','.dll','.exe','.bin')
        }
        foreach ($file in $files) {
            try { $lines = [System.IO.File]::ReadAllLines($file.FullName) } catch { continue }
            for ($lineNo=0; $lineNo -lt $lines.Count; $lineNo++) {
                foreach ($name in $signatures.Keys) {
                    if ($lines[$lineNo] -match $signatures[$name]) {
                        $rows.Add([pscustomobject]@{
                            owner_repo=$ownerRepo
                            category=$category
                            signature=$name
                            relative_file=$file.FullName.Substring($repo.FullName.Length).TrimStart('\','/')
                            line_number=($lineNo + 1)
                        })
                    }
                }
            }
        }
    }
}
$outDir = Split-Path -Parent $outPath
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$rows | Sort-Object owner_repo,relative_file,line_number,signature -Unique | Export-Csv -LiteralPath $outPath -NoTypeInformation -Encoding UTF8
Write-Output "Recorded $($rows.Count) endpoint/signature hits without storing source lines: $outPath"
