param(
    [string]$ProjectPath = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
)

$base = Join-Path $ProjectPath '选课'
$pdfRoot = Join-Path $base '02_公开资料/official'
$textRoot = Join-Path $pdfRoot 'text'
$previewRoot = Join-Path $pdfRoot 'previews'
$outPath = Join-Path $base '02_公开资料/repository_index/official_pdf_inventory.csv'
New-Item -ItemType Directory -Force -Path $textRoot,$previewRoot,(Split-Path -Parent $outPath) | Out-Null
$rows = [System.Collections.Generic.List[object]]::new()

foreach ($pdf in (Get-ChildItem -LiteralPath $pdfRoot -File -Filter '*.pdf')) {
    $stem = [System.IO.Path]::GetFileNameWithoutExtension($pdf.Name)
    $txt = Join-Path $textRoot ($stem + '.txt')
    $preview = Join-Path $previewRoot ($stem + '_p01.png')
    $status = 'ok'
    $message = ''
    try {
        & pdftotext -layout -- $pdf.FullName $txt 2>$null
        if ($LASTEXITCODE -ne 0) { throw "pdftotext exit code $LASTEXITCODE" }
        & pdftoppm -f 1 -l 1 -singlefile -png -r 120 -- $pdf.FullName ([System.IO.Path]::ChangeExtension($preview,'.tmp')) 2>$null
        # pdftoppm appends .png to the prefix.
        $rendered = ([System.IO.Path]::ChangeExtension($preview,'.tmp')) + '.png'
        if (Test-Path -LiteralPath $rendered) { Move-Item -LiteralPath $rendered -Destination $preview -Force }
        if (-not (Test-Path -LiteralPath $txt)) { throw 'text output missing' }
    } catch {
        $status = 'failed'
        $message = $_.Exception.Message
    }
    $info = (& pdfinfo -- $pdf.FullName 2>$null | Out-String)
    $pages = ''
    if ($info -match '(?m)^Pages:\s+(\d+)') { $pages = $Matches[1] }
    $textSize = if (Test-Path -LiteralPath $txt) { (Get-Item -LiteralPath $txt).Length } else { 0 }
    $previewSize = if (Test-Path -LiteralPath $preview) { (Get-Item -LiteralPath $preview).Length } else { 0 }
    $rows.Add([pscustomobject]@{
        collected_at=(Get-Date -Format 'yyyy-MM-ddTHH:mm:ssK')
        filename=$pdf.Name
        sha256=(Get-FileHash -LiteralPath $pdf.FullName -Algorithm SHA256).Hash
        pages=$pages
        status=$status
        text_path=$txt.Substring($base.Length).TrimStart('\','/')
        text_bytes=$textSize
        preview_path=$preview.Substring($base.Length).TrimStart('\','/')
        preview_bytes=$previewSize
        message=$message
    })
}
$rows | Sort-Object filename | Export-Csv -LiteralPath $outPath -NoTypeInformation -Encoding UTF8
Write-Output "Extracted $($rows.Count) official PDFs to text/previews; inventory: $outPath"
