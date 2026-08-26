param(
    [string]$ProjectPath = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
)

$base = Join-Path $ProjectPath '选课'
$rawRoot = Join-Path $base '01_本地证据/raw'
$sanRoot = Join-Path $base '01_本地证据/sanitized'
$metaRoot = Join-Path $base '01_本地证据/metadata'
New-Item -ItemType Directory -Force -Path $metaRoot | Out-Null

$fileRows = [System.Collections.Generic.List[object]]::new()
foreach ($kind in @('raw','sanitized')) {
    $root = if ($kind -eq 'raw') { $rawRoot } else { $sanRoot }
    foreach ($file in (Get-ChildItem -LiteralPath $root -Recurse -File)) {
        $fileRows.Add([pscustomobject]@{
            kind=$kind
            relative_path=$file.FullName.Substring($root.Length).TrimStart('\','/')
            size_bytes=$file.Length
            last_write_time=$file.LastWriteTime.ToString('o')
            sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
        })
    }
}
$fileRows | Sort-Object kind,relative_path | Export-Csv -LiteralPath (Join-Path $metaRoot 'file_manifest.csv') -NoTypeInformation -Encoding UTF8

$md = [System.Collections.Generic.List[string]]::new()
$md.Add('# 本地快照登记')
$md.Add('')
$md.Add('原始副本位于 `01_本地证据/raw/`，脱敏副本位于 `01_本地证据/sanitized/`。哈希见 `file_manifest.csv`。')
$md.Add('')
$md.Add('| 快照 | 来源 URL（令牌已隐藏） | 页面版本线索 | 资源文件数 | HTML 大小 | 课程行数 | 活跃标签 |')
$md.Add('|---|---|---|---:|---:|---:|---|')

foreach ($stem in @('选课','选课点击后','选课失败弹窗')) {
    $htmlPath = Join-Path (Join-Path $rawRoot $stem) ($stem + '.html')
    $assetPath = Join-Path (Join-Path $rawRoot $stem) ($stem + '_files')
    $html = [System.IO.File]::ReadAllText($htmlPath, [System.Text.Encoding]::UTF8)
    $saved = [regex]::Match($html,'saved from url=\(\d+\)([^\r\n]+)').Groups[1].Value
    $saved = $saved -replace '\s+-->.*$',''
    $saved = [regex]::Replace($saved,'([?&]token=)[^&#"''\s<>]+','$1[REDACTED_TOKEN]')
    $version = [regex]::Match($html,'https://res\.nnu\.edu\.cn/[^"''\s]+').Value
    $version = $version -replace '[&|].*$',''
    $courseRows = ([regex]::Matches($html,'class="cv-row')).Count
    $active = [regex]::Matches($html,'(?is)<li[^>]*class="[^"]*cv-active[^"]*"[^>]*>.*?<a[^>]*>(.*?)</a>') | ForEach-Object { [regex]::Replace($_.Groups[1].Value,'<[^>]+>','') -replace '\s+',' ' }
    $activeText = ($active -join '; ') -replace '\|','/'
    $assetCount = (Get-ChildItem -LiteralPath $assetPath -Recurse -File | Measure-Object).Count
    $htmlSize = (Get-Item -LiteralPath $htmlPath).Length
    $md.Add('| ' + $stem + ' | ' + $saved + ' | ' + $version + ' | ' + $assetCount + ' | ' + $htmlSize + ' | ' + $courseRows + ' | ' + $activeText + ' |')
}

$md.Add('')
$md.Add('## 已确认的页面指纹')
$md.Add('')
$md.Add('- `BaseUrl`: `https://xsxk.nnu.edu.cn:443/xsxkapp`。')
$md.Add('- `loginType`: `ldap`。')
$md.Add('- `resUrl`: `https://res.nnu.edu.cn/ver/1.8.1_TR13/products/jwfw/xsxkapp`。')
$md.Add('- 页面版权行：`© 2016 江苏金智教育信息股份有限公司`，并出现 `苏ICP备10204514号`。')
$md.Add('- 页面标签包含系统推荐、跨年级、跨专业、博雅、重修、体育、辅修、微专业和全校课程查询。')
$md.Add('- 页面快照有浏览器扩展注入的 `redeviation-bs-*` 标记；这属于采集环境噪声，分析产品前端时应单独排除。')
[System.IO.File]::WriteAllLines((Join-Path $metaRoot 'snapshot_inventory.md'),$md,[System.Text.UTF8Encoding]::new($false))

Write-Output "Wrote local file manifest and snapshot inventory to $metaRoot"
