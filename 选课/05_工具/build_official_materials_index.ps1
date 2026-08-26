param(
    [string]$ProjectPath = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
)

$base = Join-Path $ProjectPath '选课'
$textRoot = Join-Path $base '02_公开资料/official/text'
$inventory = Join-Path $base '02_公开资料/repository_index/official_pdf_inventory.csv'
$outPath = Join-Path $base '02_公开资料/repository_index/official_materials_index.md'
$keywords = @('选课','xsxkapp','yjsxkapp','金智','验证码','选课模式','选课策略','volunteer.do')
$md = [System.Collections.Generic.List[string]]::new()
$md.Add('# 官方 PDF 资料索引')
$md.Add('')
$md.Add('文本由 Poppler `pdftotext -layout` 离线生成；页面预览位于 `02_公开资料/official/previews/`。')
$md.Add('')
$md.Add('| 文件 | 页数 | 文本 | 关键字命中 |')
$md.Add('|---|---:|---:|---|')
foreach($row in (Import-Csv $inventory | Sort-Object filename)) {
    $txtPath = Join-Path $base ($row.text_path -replace '/','\')
    $text = if(Test-Path -LiteralPath $txtPath){[System.IO.File]::ReadAllText($txtPath,[System.Text.Encoding]::UTF8)}else{''}
    $hits = foreach($k in $keywords){ $n=([regex]::Matches($text,[regex]::Escape($k),'IgnoreCase')).Count; if($n -gt 0){ "${k}:$n" } }
    $relText = $row.text_path -replace '\\','/'
    $md.Add('| `' + $row.filename + '` | ' + $row.pages + ' | [' + $relText + '](' + $relText + ') | ' + ($hits -join '; ') + ' |')
}
$md.Add('')
$md.Add('## 使用提示')
$md.Add('')
$md.Add('- 先阅读与目标学校/产品版本直接相关的文件，再将同栈学校手册作为结构对照。')
$md.Add('- 文本抽取用于检索，版式结论以 PDF 和第一页预览为准。')
$md.Add('- 官方文档中的时间、入口和规则是其发布日期/版本下的资料，不直接代表 NNU 当前规则。')
[System.IO.File]::WriteAllLines($outPath,$md,[System.Text.UTF8Encoding]::new($false))
Write-Output "Wrote official materials index to $outPath"
