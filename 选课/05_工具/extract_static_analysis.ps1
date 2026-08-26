param(
    [string]$SanitizedRoot = (Join-Path (Get-Location) '选课\01_本地证据\sanitized'),
    [string]$AnalysisRoot = (Join-Path (Get-Location) '选课\04_提取分析')
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $SanitizedRoot)) {
    throw "Sanitized evidence directory was not found: $SanitizedRoot"
}
New-Item -ItemType Directory -Force -Path $AnalysisRoot | Out-Null

function Get-RelativeEvidencePath {
    param([string]$Path)
    return $Path.Substring($SanitizedRoot.Length + 1).Replace('\', '/')
}

function Get-LineNumber {
    param(
        [string[]]$Lines,
        [int]$Index
    )
    return $Index + 1
}

# 1) Session storage inventory. Values are intentionally never collected.
$storagePattern = 'sessionStorage\s*\.\s*(getItem|setItem|removeItem)\s*\(\s*[''\"]([^''\"]+)[''\"]'
$storageOccurrences = New-Object 'System.Collections.Generic.List[object]'

$sourceFiles = Get-ChildItem -LiteralPath $SanitizedRoot -Recurse -File |
    Where-Object { $_.Extension -in @('.js', '.html') }

foreach ($file in $sourceFiles) {
    $relative = Get-RelativeEvidencePath -Path $file.FullName
    $lines = [System.IO.File]::ReadAllLines($file.FullName)
    for ($i = 0; $i -lt $lines.Length; $i++) {
        foreach ($match in [regex]::Matches($lines[$i], $storagePattern)) {
            $storageOccurrences.Add([pscustomobject]@{
                Key = $match.Groups[2].Value
                Action = $match.Groups[1].Value
                File = $relative
                Line = Get-LineNumber -Lines $lines -Index $i
            })
        }
    }
}

$storageSummary = foreach ($group in ($storageOccurrences | Group-Object Key | Sort-Object Name)) {
    $references = $group.Group |
        Sort-Object File, Line |
        Select-Object -First 6 |
        ForEach-Object { '{0}:{1}' -f $_.File, $_.Line }
    [pscustomobject]@{
        Key = $group.Name
        Actions = (($group.Group.Action | Sort-Object -Unique) -join '/')
        Occurrences = $group.Count
        ExampleReferences = ($references -join '; ')
        ValueHandling = if ($group.Name -eq 'token') { 'session-only; value excluded' } else { 'JSON/string state; value excluded' }
    }
}
$storageSummary | Export-Csv -LiteralPath (Join-Path $AnalysisRoot 'session_storage_inventory.csv') -NoTypeInformation -Encoding utf8

# 2) Per-article and per-snapshot DOM counts. Only structural counts are exported.
$articleSummary = New-Object 'System.Collections.Generic.List[object]'
$snapshotSummary = New-Object 'System.Collections.Generic.List[object]'
$articlePattern = '(?s)<article\b[^>]*id="([^"]+)"[^>]*>.*?</article>'
$rowPattern = 'class\s*=\s*["''][^"'']*\bcv-row\b[^"'']*["'']'
$chosenPattern = '(?i)(?:ischoose|isChoose)\s*=\s*["'']1["'']'
$fullPattern = '(?i)isfull\s*=\s*["'']1["'']'

foreach ($snapshotDir in (Get-ChildItem -LiteralPath $SanitizedRoot -Directory | Sort-Object Name)) {
    $htmlFile = Join-Path $snapshotDir.FullName ($snapshotDir.Name + '.html')
    if (-not (Test-Path -LiteralPath $htmlFile)) { continue }
    $html = [System.IO.File]::ReadAllText($htmlFile)
    $matches = [regex]::Matches($html, $articlePattern)
    $articleCount = $matches.Count
    foreach ($article in $matches) {
        $block = $article.Value
        $articleSummary.Add([pscustomobject]@{
            Snapshot = $snapshotDir.Name
            ArticleId = $article.Groups[1].Value
            Rows = [regex]::Matches($block, $rowPattern).Count
            ChosenStates = [regex]::Matches($block, $chosenPattern).Count
            FullStates = [regex]::Matches($block, $fullPattern).Count
        })
    }
    $snapshotSummary.Add([pscustomobject]@{
        Snapshot = $snapshotDir.Name
        SanitizedHTMLBytes = ([System.IO.File]::ReadAllBytes($htmlFile)).Length
        ArticleContainers = $articleCount
        CourseRows = [regex]::Matches($html, $rowPattern).Count
        ChosenStates = [regex]::Matches($html, $chosenPattern).Count
        FullStates = [regex]::Matches($html, $fullPattern).Count
        ObservedActiveTab = if ($html -match '博雅教育课程') { 'XGXK/博雅教育课程' } else { 'not detected' }
    })
}
$articleSummary | Export-Csv -LiteralPath (Join-Path $AnalysisRoot 'snapshot_article_summary.csv') -NoTypeInformation -Encoding utf8
$snapshotSummary | Export-Csv -LiteralPath (Join-Path $AnalysisRoot 'snapshot_summary.csv') -NoTypeInformation -Encoding utf8

# 3) Static call graph. This is an evidence index, not executable request code.
$callGraph = @(
    [pscustomobject]@{ Stage = 'bootstrap'; Module = 'indexBS.js'; Function = 'queryStudentInformation'; Method = 'GET'; Endpoint = '/sys/xsxkapp/student/{studentCode}.do'; RequestShape = 'student code in path + timestamp'; AuthState = 'token header'; ResponseTransition = 'populate studentInfo/electiveBatch context'; Evidence = '选课点击后/选课点击后_files/indexBS.js:2-10'; Confidence = 'direct-local' }
    [pscustomobject]@{ Stage = 'bootstrap'; Module = 'indexBS.js'; Function = 'queryTestBatch'; Method = 'GET'; Endpoint = '/sys/xsxkapp/elective/batch.do'; RequestShape = 'timestamp'; AuthState = 'no explicit token argument'; ResponseTransition = 'available elective batches'; Evidence = '选课点击后/选课点击后_files/indexBS.js:23-30'; Confidence = 'direct-local' }
    [pscustomobject]@{ Stage = 'bootstrap'; Module = 'indexBS.js'; Function = 'querySysParam'; Method = 'GET sync'; Endpoint = '/sys/xsxkapp/publicinfo/sysparam.do'; RequestShape = 'timestamp; synchronous AJAX'; AuthState = 'no explicit token argument'; ResponseTransition = 'feature/menu/textbook switches'; Evidence = '选课点击后/选课点击后_files/indexBS.js:50-56'; Confidence = 'direct-local' }
    [pscustomobject]@{ Stage = 'bootstrap'; Module = 'loginInUserRegister.js'; Function = 'loginInUserRegister'; Method = 'GET'; Endpoint = '/sys/xsxkapp/student/register.do'; RequestShape = 'number query parameter'; AuthState = 'session established by SSO page'; ResponseTransition = 'store token and studentInfo when registration succeeds'; Evidence = '选课点击后/选课点击后_files/loginInUserRegister.js:1-53'; Confidence = 'direct-local' }
    [pscustomobject]@{ Stage = 'bootstrap'; Module = 'indexBS.js'; Function = 'queryVocdeToken'; Method = 'GET'; Endpoint = '/sys/xsxkapp/student/4/vcode.do'; RequestShape = 'timestamp'; AuthState = 'no explicit token argument'; ResponseTransition = 'captcha/token precondition'; Evidence = '选课点击后/选课点击后_files/indexBS.js:91-97'; Confidence = 'direct-local' }
    [pscustomobject]@{ Stage = 'menu'; Module = 'grablessons.js'; Function = 'pageHeadTabChange/initMenuControl'; Method = 'local'; Endpoint = 'course-type tabs'; RequestShape = 'teachingClassType in sessionStorage'; AuthState = 'currentBatch + sysParam'; ResponseTransition = 'dispatch listInit for each course category'; Evidence = '选课点击后/选课点击后_files/grablessons.js:2824-2886; 4641-4703'; Confidence = 'direct-local' }
    [pscustomobject]@{ Stage = 'query'; Module = 'xsxkpub.js'; Function = 'queryRecommendedCourse'; Method = 'POST'; Endpoint = '/sys/xsxkapp/elective/recommendedCourse.do'; RequestShape = 'querySetting'; AuthState = 'token header'; ResponseTransition = 'render recommended course rows/cards'; Evidence = '选课点击后/选课点击后_files/xsxkpub.js:77-85'; Confidence = 'direct-local' }
    [pscustomobject]@{ Stage = 'query'; Module = 'xsxkpub.js'; Function = 'queryProgramCourse'; Method = 'POST'; Endpoint = '/sys/xsxkapp/elective/programCourse.do'; RequestShape = 'querySetting'; AuthState = 'token header'; ResponseTransition = 'render plan/unplan/retake/sport/minor/micro rows'; Evidence = '选课点击后/选课点击后_files/xsxkpub.js:115-123'; Confidence = 'direct-local' }
    [pscustomobject]@{ Stage = 'query'; Module = 'xsxkpub.js'; Function = 'queryPublicCourse'; Method = 'POST'; Endpoint = '/sys/xsxkapp/elective/publicCourse.do'; RequestShape = 'querySetting'; AuthState = 'token header'; ResponseTransition = 'render public-course table'; Evidence = '选课点击后/选课点击后_files/xsxkpub.js:102-110'; Confidence = 'direct-local' }
    [pscustomobject]@{ Stage = 'query'; Module = 'xsxkpub.js'; Function = 'queryCourseData'; Method = 'POST'; Endpoint = '/sys/xsxkapp/elective/queryCourse.do'; RequestShape = 'querySetting'; AuthState = 'token header'; ResponseTransition = 'render all-school query rows'; Evidence = '选课点击后/选课点击后_files/xsxkpub.js:222-230'; Confidence = 'direct-local' }
    [pscustomobject]@{ Stage = 'query'; Module = 'grablessons.js'; Function = 'buildQueryTCParam'; Method = 'local'; Endpoint = 'querySetting wrapper'; RequestShape = 'studentCode,campus,electiveBatchCode,isMajor,teachingClassType,queryContent,pageSize,pageNumber,order'; AuthState = 'sessionStorage studentInfo/currentCampus'; ResponseTransition = 'typed filter prefixes and list endpoint selected'; Evidence = '选课点击后/选课点击后_files/grablessons.js:4346-4588'; Confidence = 'direct-local' }
    [pscustomobject]@{ Stage = 'guard'; Module = 'grablessons.js'; Function = 'selectPublicCourse/checkSfkxqSelect'; Method = 'local'; Endpoint = '/sys/xsxkapp/elective/batchisopen.do (fallback check)'; RequestShape = 'xklcdm; campus/teaching-campus attributes'; AuthState = 'sessionStorage currentBatch/sysParam/studentInfo'; ResponseTransition = 'open/campus/conflict checks before operation'; Evidence = '选课点击后/选课点击后_files/grablessons.js:624-712'; Confidence = 'direct-local' }
    [pscustomobject]@{ Stage = 'guard'; Module = 'xsxkpub.js'; Function = 'querySfCanChoose'; Method = 'GET'; Endpoint = '/sys/xsxkapp/util/canchoose.do'; RequestShape = 'xh,jxbid,xklcdm,timestamp'; AuthState = 'token header'; ResponseTransition = 'eligibility check'; Evidence = '选课点击后/选课点击后_files/xsxkpub.js:266-275'; Confidence = 'direct-local' }
    [pscustomobject]@{ Stage = 'mutate'; Module = 'grablessons.js'; Function = 'buildAddVolunteerParam/addVolunteer'; Method = 'POST'; Endpoint = '/sys/xsxkapp/elective/volunteer.do'; RequestShape = 'addParam wrapping data: operationType=1, studentCode, electiveBatchCode, teachingClassId, isMajor, campus, teachingClassType, optional needBook/testTeachingClassID'; AuthState = 'token header + browser session'; ResponseTransition = 'code=1 means accepted for asynchronous processing'; Evidence = '选课点击后/选课点击后_files/grablessons.js:4596-4637; xsxkpub.js:142-150'; Confidence = 'direct-local' }
    [pscustomobject]@{ Stage = 'mutate'; Module = 'xsxkpub.js'; Function = 'queryOperateProcess/initProcessInterval'; Method = 'POST'; Endpoint = '/sys/xsxkapp/elective/studentstatus.do'; RequestShape = 'studentCode'; AuthState = 'token header + browser session'; ResponseTransition = 'code=1 success, code=-1 failure, otherwise retry about once per second up to ten attempts'; Evidence = '选课点击后/选课点击后_files/xsxkpub.js:407-461'; Confidence = 'direct-local' }
    [pscustomobject]@{ Stage = 'mutate'; Module = 'grablessons.js'; Function = 'deleteVolunteer/deleteVolunteerResult'; Method = 'GET'; Endpoint = '/sys/xsxkapp/elective/deleteVolunteer.do'; RequestShape = 'deleteParam wrapping data: operationType=2, studentCode, electiveBatchCode, teachingClassId, isMajor'; AuthState = 'token header + browser session'; ResponseTransition = 'accepted response then same status polling; refresh row/capacity/count'; Evidence = '选课点击后/选课点击后_files/grablessons.js:2584-2637; selectedcourseBS.js:18-28'; Confidence = 'direct-local' }
    [pscustomobject]@{ Stage = 'refresh'; Module = 'grablessonsBS.js'; Function = 'queryTeachingClassCapacity/flushTeachingClassCapacity'; Method = 'GET'; Endpoint = '/sys/xsxkapp/elective/teachingclass/capacity.do'; RequestShape = 'teachingClassId,capacitySuffix,xh,timestamp'; AuthState = 'token header'; ResponseTransition = 'update full/remaining/gender capacity in DOM'; Evidence = '选课点击后/选课点击后_files/grablessonsBS.js:4-14; grablessons.js:5253-5338'; Confidence = 'direct-local' }
    [pscustomobject]@{ Stage = 'result'; Module = 'selectedcourseBS.js'; Function = 'queryChooseCourse'; Method = 'GET'; Endpoint = '/sys/xsxkapp/elective/courseResult.do'; RequestShape = 'studentCode,electiveBatchCode,timestamp'; AuthState = 'token header'; ResponseTransition = 'render selected result and count non-test rows'; Evidence = '选课点击后/选课点击后_files/selectedcourseBS.js:4-16; grablessons.js:5226-5247'; Confidence = 'direct-local' }
    [pscustomobject]@{ Stage = 'result'; Module = 'departurelogBS.js'; Function = 'queryStudentReturnResults'; Method = 'GET'; Endpoint = '/sys/xsxkapp/elective/returnResults.do'; RequestShape = 'studentCode,electiveBatchCode,timestamp'; AuthState = 'token header'; ResponseTransition = 'render operation/withdrawal result log'; Evidence = '选课点击后/选课点击后_files/departurelogBS.js:1-10; departurelog.js:41-70'; Confidence = 'direct-local' }
    [pscustomobject]@{ Stage = 'state'; Module = 'bh_utils.js'; Function = 'BH_UTILS.doAjax'; Method = 'generic'; Endpoint = 'all wrapped endpoints'; RequestShape = 'jQuery AJAX data object; JSON response'; AuthState = 'caller-supplied headers, usually token'; ResponseTransition = 'redirect on loginURL; reject on transport errors'; Evidence = '选课点击后/选课点击后_files/bh_utils.js:338-400'; Confidence = 'direct-local' }
)
$callGraph | Export-Csv -LiteralPath (Join-Path $AnalysisRoot 'static_call_graph.csv') -NoTypeInformation -Encoding utf8

# 4) Evidence correspondence with public source snapshots. No code is executed here.
$sourceMatrix = @(
    [pscustomobject]@{ Repository = 'guh0613/ehall-backend'; Category = 'NNU direct'; Relation = 'NNU authentication/eHall context'; ObservedPatterns = 'authserver.nnu.edu.cn, ehall.nnu.edu.cn, ehallapp.nnu.edu.cn and xsxk.nnu.edu.cn course-select URL; authToken-based backend services'; EvidenceFiles = '03_仓库源码/00_nnu_direct/guh0613__ehall-backend/configs/config.py; handlers/login_handler.py'; Confidence = 'direct-context'; Boundary = 'not the exact grablessons front-end implementation' }
    [pscustomobject]@{ Repository = 'XingHeYuZhuan/shiguang_warehouse'; Category = 'NNU direct'; Relation = 'NNU eHall schedule adapter'; ObservedPatterns = 'NNU eHall course-table endpoints and CAS host references'; EvidenceFiles = '03_仓库源码/00_nnu_direct/XingHeYuZhuan__shiguang_warehouse/resources/NJNU/njnu.js; resources/NJNU/adapters.yaml'; Confidence = 'direct-context'; Boundary = 'schedule import context, not selection operation semantics' }
    [pscustomobject]@{ Repository = 'GreenTeodoro839/NJU-xk-helper'; Category = 'same WISEDU stack'; Relation = 'closest behavioral correspondence'; ObservedPatterns = 'volunteer.do operationType=1; studentstatus.do polling; vcode/login paths; session-expiry handling; client-side addParam transformation'; EvidenceFiles = '03_仓库源码/01_same_stack/GreenTeodoro839__NJU-xk-helper/xk.py; lib/common.py; lib/authenticator.py'; Confidence = 'strong-similarity'; Boundary = 'NJU deployment; do not assume its encryption or field variants apply to NNU' }
    [pscustomobject]@{ Repository = 'HansZ8/BIT-XK-WISEDU'; Category = 'same WISEDU stack'; Relation = 'login and mutate-flow correspondence'; ObservedPatterns = 'student/4/vcode.do, student/check/login.do, elective/volunteer.do, operationType=1 and teachingClassId'; EvidenceFiles = '03_仓库源码/01_same_stack/HansZ8__BIT-XK-WISEDU/xk.py'; Confidence = 'strong-similarity'; Boundary = 'BIT deployment and older client; not NNU proof' }
    [pscustomobject]@{ Repository = 'Weeye-hua/SZU-Course-Help'; Category = 'same WISEDU stack'; Relation = 'query and add payload correspondence'; ObservedPatterns = 'programCourse.do/recommendedCourse.do with querySetting; volunteer.do with nested data and token/Cookie headers'; EvidenceFiles = '03_仓库源码/01_same_stack/Weeye-hua__SZU-Course-Help/course_list.py; choose_course.py'; Confidence = 'strong-similarity'; Boundary = 'SZU deployment; payload adds fields not present in the local NNU builder' }
    [pscustomobject]@{ Repository = 'AriaPokotengYe/SEU-NewSystem-catcher'; Category = 'same WISEDU stack'; Relation = 'endpoint vocabulary correspondence'; ObservedPatterns = 'recommendedCourse.do, publicCourse.do, programCourse.do, volunteer.do and vcode path'; EvidenceFiles = '03_仓库源码/01_same_stack/AriaPokotengYe__SEU-NewSystem-catcher/crawl.py'; Confidence = 'supporting-similarity'; Boundary = 'SEU deployment and old client' }
    [pscustomobject]@{ Repository = 'neiro-o/seuGrabber'; Category = 'same WISEDU stack'; Relation = 'course selection endpoint correspondence'; ObservedPatterns = 'xsxkapp and volunteer.do signatures in static client code'; EvidenceFiles = '03_仓库源码/01_same_stack/neiro-o__seuGrabber'; Confidence = 'supporting-similarity'; Boundary = 'repository-wide fingerprint; exact flow requires manual file-level review' }
    [pscustomobject]@{ Repository = 'YHalo-wyh/YNU-xk_spider-Pro'; Category = 'same WISEDU stack'; Relation = 'endpoint vocabulary correspondence'; ObservedPatterns = 'xsxkapp/volunteer/recommended/vcode signatures'; EvidenceFiles = '03_仓库源码/01_same_stack/YHalo-wyh__YNU-xk_spider-Pro'; Confidence = 'supporting-similarity'; Boundary = 'YNU deployment; fingerprint evidence only at this stage' }
)
$sourceMatrix | Export-Csv -LiteralPath (Join-Path $AnalysisRoot 'source_correspondence_matrix.csv') -NoTypeInformation -Encoding utf8

Write-Output ('Generated static analysis artifacts in ' + $AnalysisRoot)
