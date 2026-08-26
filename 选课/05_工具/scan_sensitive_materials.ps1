param(
    [string]$ProjectPath = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
)

$base = Join-Path $ProjectPath '选课'
$scanRoots = @(
    (Join-Path $base '03_仓库源码'),
    (Join-Path $base '01_本地证据/sanitized'),
    (Join-Path $base '02_公开资料/gist_greasyfork')
)
$outPath = Join-Path $base '04_提取分析/sensitive_materials_scan.csv'
$patterns = [ordered]@{
    password='password|passwd|pwd'
    secret='secret|client_secret|private_key'
    token='access[_-]?token|authorization|sessionStorage\.token|[?&]token='
    cookie='cookie'
    identifier='studentCode|studentcode|学号'
}
$rows = [System.Collections.Generic.List[object]]::new()
foreach ($root in $scanRoots) {
    if (-not (Test-Path -LiteralPath $root)) { continue }
    foreach ($name in $patterns.Keys) {
        $matches = & rg -i -n -l --hidden --glob '!.git/**' --glob '!*.png' --glob '!*.jpg' --glob '!*.jpeg' --glob '!*.pdf' -- $patterns[$name] $root 2>$null
        if ($LASTEXITCODE -eq 0 -and $matches) {
            foreach ($file in @($matches)) {
                $rows.Add([pscustomobject]@{
                    scan_root=$root.Substring($base.Length).TrimStart('\','/')
                    category=$name
                    relative_file=$file.Substring($root.Length).TrimStart('\','/')
                    note='命中字段/代码模式；未保存匹配行或具体值'
                })
            }
        }
    }
}
$outDir = Split-Path -Parent $outPath
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$rows | Sort-Object scan_root,category,relative_file -Unique | Export-Csv -LiteralPath $outPath -NoTypeInformation -Encoding UTF8
Write-Output "Recorded $($rows.Count) sensitive-pattern file hits to $outPath"
