#Requires -Version 5.1
<#
.SYNOPSIS
  把当前开发机上的 AomeRAG 打包成「便携瘦包」AomeRAG-Server-<date>/。

  打包产物交给目标 Win10 机器后：解压 → 双击「启动.bat」即可。
  目标机器不需要装 Python/Node，Ollama 与 bge-m3 模型由「启动.bat」首次自动下载。

.NOTES
  运行于开发机（有 .venv、可构建前端）。用法：
    powershell -ExecutionPolicy Bypass -File deploy\build_bundle.ps1
  常用参数：
    -ApiKey "sk-xxx"        指定 DeepSeek key（默认读取开发机 .env）
    -SkipFrontend           跳过 npm run build（web/dist 已存在时）
    -SkipCheck              跳过打包后离线自检
    -Zip                    打包完后额外压成 AomeRAG-Server-<date>.zip
#>
# 手动解析参数（不用 param 块）：PowerShell 5.1 在「带 param 块的脚本被调用、
# 且后续用位置参数调用 cmdlet」时存在参数绑定 bug（把字符串误绑到 [switch] 参数）。
# 去掉 param 块、从 $args 解析可彻底规避。
$ProjectRoot   = ''
$ApiKey        = ''
$PandocVersion = '3.1.11'
$SkipFrontend  = $false
$SkipCheck     = $false
$Zip           = $false
for ($i = 0; $i -lt $args.Count; $i++) {
    switch ($args[$i]) {
        '-ProjectRoot'   { $i++; if ($i -lt $args.Count) { $ProjectRoot = $args[$i] } }
        '-ApiKey'        { $i++; if ($i -lt $args.Count) { $ApiKey = $args[$i] } }
        '-PandocVersion' { $i++; if ($i -lt $args.Count) { $PandocVersion = $args[$i] } }
        '-SkipFrontend'  { $SkipFrontend = $true }
        '-SkipCheck'     { $SkipCheck = $true }
        '-Zip'           { $Zip = $true }
    }
}
if (-not $ProjectRoot) { $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path }

$ErrorActionPreference = 'Stop'

# 打包时若开发机正在跑 aomerag（8000 端口），拷到的 zvec 可能是写一半的快照
$listening = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($listening) {
    Write-Warning "检测到 8000 端口有服务在跑（可能是开发服务器）。建议先停掉再打包，"
    Write-Warning "否则 data/zvec 索引可能拷到写一半的快照。可继续（结果需自行确认）。"
}

$date = Get-Date -Format 'yyyyMMdd'
$OutRoot = Join-Path $PSScriptRoot 'out'
$BundleName = "AomeRAG-Server-$date"
$Out = Join-Path $OutRoot $BundleName

function Step($m) { Write-Host "`n== $m" -ForegroundColor Cyan }
function Die($m) { Write-Host "!! $m" -ForegroundColor Red; exit 1 }

# ---------- 0. 输出目录 ----------
Step "输出目录: $Out"
if (Test-Path $Out) { Remove-Item $Out -Recurse -Force }
New-Item -ItemType Directory -Force -Path $Out | Out-Null

# ---------- 1. 前置检查 ----------
Step "前置检查"
$venvPy = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPy)) { Die "未找到 .venv（$venvPy）。请先 uv sync 装好依赖。" }

$envFile = Join-Path $ProjectRoot '.env'
if (-not (Test-Path $envFile)) { Die "未找到 .env。请先 cp .env.example .env 并填入 DEEPSEEK_API_KEY。" }
$envText = Get-Content $envFile -Raw
if ($envText -notmatch '(?m)^DEEPSEEK_API_KEY=.+') { Die ".env 中 DEEPSEEK_API_KEY 为空，请先填入再打包。" }
if (-not $ApiKey) { $ApiKey = ([regex]::Match($envText, '(?m)^DEEPSEEK_API_KEY=(.*)')).Groups[1].Value.Trim() }
Write-Host "  DeepSeek key: ${($ApiKey.Substring(0,4))}*** 长度=$($ApiKey.Length)"

$zvecDir = Join-Path $ProjectRoot 'data\zvec'
if (-not (Test-Path (Join-Path $zvecDir 'manifest*'))) {
    Die "data/zvec 为空：请先在开发机对知识库跑 /ingest/dir（或 /admin 切片）建好向量索引再打包。"
}
$mdDir = Join-Path $ProjectRoot 'raw\md-data'
if (-not (Test-Path $mdDir) -or -not (Get-ChildItem $mdDir -Filter *.md -ErrorAction SilentlyContinue).Count) {
    Write-Warning "raw/md-data 为空。注意：服务器 /admin 的『清洗』是全量重生成，若 raw/raw-data 也没有原始文件，点击会清空 md-data。"
}

# ---------- 2. 前端构建 ----------
if (-not $SkipFrontend) {
    Step "构建前端 (web/dist)"
    Push-Location (Join-Path $ProjectRoot 'web')
    try {
        if (-not (Test-Path 'node_modules')) { Write-Host "  npm install ..."; & npm install | Out-Null }
        & npm run build
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path 'dist\index.html')) { Die "npm run build 失败。" }
    } finally { Pop-Location }
}

# ---------- 3. 便携 Python ----------
Step "复制便携 Python（venv 的 base，CPython 3.12 win-x64）"
$pyvenvCfg = Join-Path $ProjectRoot '.venv\pyvenv.cfg'
$basePy = ((Get-Content $pyvenvCfg | Where-Object { $_ -match '^home\s*=' }) -replace '^home\s*=\s*', '').Trim()
if (-not $basePy -or -not (Test-Path (Join-Path $basePy 'python.exe'))) {
    Die "未找到便携 Python base: $basePy"
}
robocopy $basePy (Join-Path $Out 'runtime\python') /E /NFL /NDL /NJH /NJS /XD "__pycache__" ".git" /XF "*.pyc" | Out-Null
if ($LASTEXITCODE -ge 8) { Die "复制 portable python 失败" }

# ---------- 4. venv 依赖 → 便携 Python ----------
Step "复制 venv 依赖（排除本地可编辑安装）"
$venvSite = Join-Path $ProjectRoot '.venv\Lib\site-packages'
$outSite  = Join-Path $Out 'runtime\python\Lib\site-packages'
robocopy $venvSite $outSite /E /NFL /NDL /NJH /NJS /XD "__pycache__" "*.dist-info" /XF "*.pyc" "__editable__*" "_editable_impl*" "*.egg-link" | Out-Null
if ($LASTEXITCODE -ge 8) { Die "复制 site-packages 失败" }

# 中和 magika 的 dotenv 副作用：magika/__init__.py 在 import 时会执行
# dotenv.load_dotenv(dotenv.find_dotenv())，把目录树上最近的 .env（可能是别的
# 项目/开发机的）灌进环境变量；而 pydantic-settings 里环境变量优先于 .env 文件，
# 会把本包的 .env 覆盖掉（曾导致服务器把 DEEPSEEK_MODEL 读成 deepseek-v4-flash）。
$magikaInit = Join-Path $outSite 'magika\__init__.py'
if (Test-Path $magikaInit) {
    $mRaw  = Get-Content $magikaInit -Raw
    $mNew  = $mRaw.Replace(
        'dotenv.load_dotenv(dotenv.find_dotenv())',
        '# [aome-rag] magika dotenv side-effect neutralized'
    )
    if ($mNew -eq $mRaw) {
        Write-Warning "警告：magika/__init__.py 未找到预期行，dotenv 副作用未被中和（magika 版本可能变了）"
    } else {
        Set-Content -Path $magikaInit -Value $mNew -Encoding UTF8
        Write-Host "  已中和 magika 的 dotenv 副作用（防环境变量污染）"
    }
}

# ---------- 5. app 目录 ----------
Step "复制 app（src / web/dist / data/zvec / raw / .env）"
$app = Join-Path $Out 'app'
New-Item -ItemType Directory -Force -Path $app | Out-Null

robocopy (Join-Path $ProjectRoot 'src')            (Join-Path $app 'src')        /E /NFL /NDL /NJH /NJS /XD "__pycache__" /XF "*.pyc" | Out-Null
robocopy (Join-Path $ProjectRoot 'web\dist')       (Join-Path $app 'web\dist')   /E /NFL /NDL /NJH /NJS | Out-Null
robocopy $zvecDir                                  (Join-Path $app 'data\zvec')  /E /NFL /NDL /NJH /NJS | Out-Null
if (Test-Path (Join-Path $ProjectRoot 'raw'))      { robocopy (Join-Path $ProjectRoot 'raw') (Join-Path $app 'raw') /E /NFL /NDL /NJH /NJS | Out-Null }
if (Test-Path (Join-Path $ProjectRoot 'skills'))   { robocopy (Join-Path $ProjectRoot 'skills') (Join-Path $app 'skills') /E /NFL /NDL /NJH /NJS | Out-Null }

$newEnv = @"
DEEPSEEK_API_KEY=$ApiKey
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
MAX_CONCURRENT_LLM=8
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBED_MODEL=bge-m3
EMBED_DIM=1024
MAX_CONCURRENT_EMBEDS=4
ZVEC_PATH=./data/zvec
KB_COLLECTION=kb_chunks_v1
TOP_K=6
DENSE_WEIGHT=0.7
FTS_WEIGHT=0.3
MAX_CONCURRENT_LOOPS=16
MAX_ITERATIONS=6
SQLITE_PATH=./data/sessions.db
SKILLS_DIR=./skills
RAW_DATA_DIR=./raw/raw-data
MD_DATA_DIR=./raw/md-data
FRONTEND_DIST=./web/dist
LOG_LEVEL=INFO
"@
# ASCII 无 BOM：避免 python-dotenv 把首个 key 读成 "DEEPSEEK_API_KEY"
Set-Content -Path (Join-Path $app '.env') -Value $newEnv -Encoding Ascii

# ---------- 6. 便携 Pandoc ----------
Step "便携 Pandoc (tools/pandoc.exe)"
$toolsDir = Join-Path $Out 'tools'
New-Item -ItemType Directory -Force -Path $toolsDir | Out-Null
$pandocExe = Join-Path $toolsDir 'pandoc.exe'
if (-not (Test-Path $pandocExe)) {
    $zip = Join-Path $OutRoot "pandoc-$PandocVersion.zip"
    $url = "https://github.com/jgm/pandoc/releases/download/$PandocVersion/pandoc-$PandocVersion-windows-x86_64.zip"
    Write-Host "  下载 Pandoc $PandocVersion (~30MB) ..."
    Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
    Expand-Archive $zip -DestinationPath $OutRoot -Force
    $pandocSrc = Get-ChildItem (Join-Path $OutRoot "pandoc-$PandocVersion") -Recurse -Filter 'pandoc.exe' |
        Select-Object -First 1
    if (-not $pandocSrc) { Die "解压的 Pandoc zip 里找不到 pandoc.exe" }
    Copy-Item $pandocSrc.FullName $pandocExe
    Remove-Item $zip, (Join-Path $OutRoot "pandoc-$PandocVersion") -Recurse -Force
}
Write-Host "  $((Get-Item $pandocExe).Name) 就绪"

# ---------- 7. 服务器脚本 + updates 目录 ----------
Step "复制启动脚本"
robocopy (Join-Path $PSScriptRoot 'server') $Out /E /NFL /NDL /NJH /NJS | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Out 'updates\applied') | Out-Null

# ---------- 8. 离线自检 ----------
if (-not $SkipCheck) {
    Step "自检：用包内 Python 启动 app，验证向量库可重定位加载"
    $checkPy = Join-Path $Out 'selfcheck.py'
    $code = @'
import sys, os
from fastapi.testclient import TestClient
from aome_rag.main import create_app
app = create_app()
with TestClient(app) as c:
    r = c.get('/stats', headers={'X-User-Id': 'selfcheck'})
    assert r.status_code == 200, r.text
    j = r.json()
    n = j.get('n_chunks', 0)
    model = j.get('llm_model')
    print('SELFCHECK n_chunks =', n, 'model =', model)
    assert n > 0, '向量索引为空，打包的知识库无效'
    assert model == 'deepseek-chat', f'LLM 模型被外部 .env 污染（应为 deepseek-chat，实际 {model}）'
print('SELFCHECK OK')
'@
    Set-Content -Path $checkPy -Value $code -Encoding utf8
    Push-Location $Out
    try {
        $env:PYTHONPATH = (Join-Path $Out 'app\src')
        & (Join-Path $Out 'runtime\python\python.exe') $checkPy
        if ($LASTEXITCODE -ne 0) { Die "自检失败：应用无法从包内启动，请勿交付此包。" }
    } finally {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
        Pop-Location
    }
    Remove-Item $checkPy -Force
    # 自检会创建空会话库，交付时删掉让服务器全新开始
    Remove-Item (Join-Path $app 'data\sessions.db') -Force -ErrorAction SilentlyContinue
}

# ---------- 9. 完成 ----------
Step "完成"
$sizeMB = [math]::Round((Get-ChildItem $Out -Recurse -File | Measure-Object Length -Sum).Sum / 1MB, 1)
Write-Host "打包完成: $Out  ($sizeMB MB)" -ForegroundColor Green
Write-Host "下一步: 把整个 $BundleName 文件夹拷贝到目标 Win10 机器，解压后双击『启动.bat』。"

if ($Zip) {
    $zipPath = Join-Path $OutRoot "$BundleName.zip"
    Write-Host "  压缩中 ..."
    Compress-Archive -Path (Join-Path $Out '*') -DestinationPath $zipPath -Force
    $zMB = [math]::Round((Get-Item $zipPath).Length / 1MB, 1)
    Write-Host "  已压缩: $zipPath  ($zMB MB)" -ForegroundColor Green
}
