param(
    [string]$ProjectPath = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
)

$base = Join-Path $ProjectPath '选课'
$matrixPath = Join-Path $base '04_提取分析/repository_fingerprint_matrix.csv'
$outPath = Join-Path $base '04_提取分析/repository_review_queue.md'
if (-not (Test-Path -LiteralPath $matrixPath)) { throw "Fingerprint matrix not found: $matrixPath" }

$rows = Import-Csv -LiteralPath $matrixPath | ForEach-Object {
    $score = 0
    $score += 5 * [int]$_.xsxkapp_files
    $score += 4 * [int]$_.volunteer_do_files
    $score += 3 * [int]$_.vcode_do_files
    $score += 2 * [int]$_.recommendedCourse_do_files
    $score += 2 * [int]$_.publicCourse_do_files
    $score += 2 * [int]$_.programCourse_do_files
    $score += 2 * [int]$_.xkxf_do_files
    $score += 5 * [int]$_.nnu_domain_files
    $score += 2 * [int]$_.njnu_domain_files
    $_ | Add-Member -NotePropertyName static_match_score -NotePropertyValue $score -PassThru
} | Sort-Object {[int]$_.static_match_score}, {[int]$_.xsxkapp_files} -Descending

$md = [System.Collections.Generic.List[string]]::new()
$md.Add('# 仓库静态复核队列')
$md.Add('')
$md.Add('排名仅按本地源码中的字符串命中计算，用于安排人工阅读顺序，不代表代码质量、当前可用性或对 NNU 的实际兼容性。所有仓库都不执行。')
$md.Add('')
$md.Add('| 顺序 | 仓库 | 分组 | xsxkapp 文件 | volunteer.do 文件 | vcode 文件 | NNU 域名文件 | 评分 |')
$md.Add('|---:|---|---|---:|---:|---:|---:|---:|')
$i=0
foreach($row in ($rows | Select-Object -First 25)) {
    $i++
    $md.Add("| $i | $($row.owner_repo) | $($row.category) | $($row.xsxkapp_files) | $($row.volunteer_do_files) | $($row.vcode_do_files) | $($row.nnu_domain_files) | $($row.static_match_score) |")
}
$md.Add('')
$md.Add('## 人工复核字段')
$md.Add('')
$md.Add('- `base URL`、登录/验证码路径、请求方法和请求头处理。')
$md.Add('- 轮次/批次字段、课程查询 `querySetting` 结构和教学班字段。')
$md.Add('- `volunteer.do`、退选和结果轮询的请求/响应模型。')
$md.Add('- 令牌、Cookie、密码、验证码和个人标识的处理方式；只记录模式，不复制值。')
$md.Add('- 许可证、依赖、更新时间和明显的版本漂移。')
[System.IO.File]::WriteAllLines($outPath,$md,[System.Text.UTF8Encoding]::new($false))
Write-Output "Wrote review queue to $outPath"
