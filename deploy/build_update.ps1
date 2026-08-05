#Requires -Version 5.1
<#
.SYNOPSIS
  生成「更新包」zip。更新包放到服务器 updates\ 文件夹后，双击「重启.bat」即可应用。

.PARAMETER Type
  kb  知识库更新：data/zvec 索引 + raw/md-data（新增/修改文档后，先在开发机跑过
      /ingest/dir 或 /admin 切片再打）。
  app 应用代码更新：src + web/dist（改代码后需先 npm run build）。

  更新包内容以 app\ 为根（zip 内是 data\... 、src\... 等），重启.bat 会解压覆盖到 app\。
  会话历史 data/sessions.db 不会被动到。

  打包后自动自检（用开发机 venv 起 app）：kb 断言索引 n_chunks>0，app 验证新代码可启动；
  自检失败会拒绝生成。可用 -SkipCheck 跳过（不建议）。

.NOTES
  用法：
    powershell -ExecutionPolicy Bypass -File deploy\build_update.ps1 -Type kb
    powershell -ExecutionPolicy Bypass -File deploy\build_update.ps1 -Type app
    powershell -ExecutionPolicy Bypass -File deploy\build_update.ps1 -Type app -SkipCheck
#>
# 手动解析参数（同 build_bundle.ps1，规避 PS 5.1 的 param 块 + 位置参数绑定 bug）
$ProjectRoot = ''
$Type        = 'kb'
$OutDir      = ''
$SkipCheck   = $false
for ($i = 0; $i -lt $args.Count; $i++) {
    switch ($args[$i]) {
        '-ProjectRoot' { $i++; if ($i -lt $args.Count) { $ProjectRoot = $args[$i] } }
        '-Type'        { $i++; if ($i -lt $args.Count) { $Type = $args[$i] } }
        '-OutDir'      { $i++; if ($i -lt $args.Count) { $OutDir = $args[$i] } }
        '-SkipCheck'   { $SkipCheck = $true }
    }
}
if (-not $ProjectRoot) { $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path }
if (-not $OutDir)      { $OutDir = Join-Path $PSScriptRoot 'out' }
$OutDir = [System.IO.Path]::GetFullPath($OutDir)  # 转绝对路径，避免 Push-Location 后相对路径错乱
if ($Type -notin @('kb', 'app')) { Write-Host "!! -Type 仅支持 kb / app"; exit 1 }

# 打包时若开发机正在跑 aomerag（8000 端口），拷到的 zvec 可能是写一半的快照
$listening = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($listening) {
    Write-Warning "检测到 8000 端口有服务在跑（可能是开发服务器）。建议先停掉再打包，"
    Write-Warning "否则 data/zvec 索引可能拷到写一半的快照（kb 更新包的自检可能因此失败）。"
}

$ErrorActionPreference = 'Stop'

function Step($m) { Write-Host "`n== $m" -ForegroundColor Cyan }
function Die($m) { Write-Host "!! $m" -ForegroundColor Red; exit 1 }

$stamp = Get-Date -Format 'yyyyMMdd-HHmm'
$zip = Join-Path $OutDir "update-$Type-$stamp.zip"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$stage = Join-Path $OutDir "stage-update-$Type"
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Force -Path $stage | Out-Null

if ($Type -eq 'kb') {
    $zvecDir = Join-Path $ProjectRoot 'data\zvec'
    if (-not (Test-Path (Join-Path $zvecDir 'manifest*'))) {
        throw "data/zvec 为空：请先在开发机对知识库跑 /ingest/dir 建好索引。"
    }
    robocopy $zvecDir (Join-Path $stage 'data\zvec') /E /NFL /NDL /NJH /NJS | Out-Null
    robocopy (Join-Path $ProjectRoot 'raw\md-data') (Join-Path $stage 'raw\md-data') /E /NFL /NDL /NJH /NJS | Out-Null
    Write-Host "正在打包知识库更新（zvec + md-data）..." -ForegroundColor Cyan
} else {
    robocopy (Join-Path $ProjectRoot 'src') (Join-Path $stage 'src') /E /NFL /NDL /NJH /NJS /XD "__pycache__" /XF "*.pyc" | Out-Null
    if (Test-Path (Join-Path $ProjectRoot 'web\dist')) {
        robocopy (Join-Path $ProjectRoot 'web\dist') (Join-Path $stage 'web\dist') /E /NFL /NDL /NJH /NJS | Out-Null
    } else {
        Write-Warning "web/dist 不存在，前端部分被跳过（请先 npm run build）。"
    }
    Write-Host "正在打包应用代码更新（src + web/dist）..." -ForegroundColor Cyan
}

# ---------- 自检：用开发机 venv 起 app，验证更新包内容能正常加载 ----------
# kb：用开发机现有 src 打开 stage 里的 zvec（验证索引本身有效，要求 n_chunks>0）
# app：用 stage 里的新 src 打开一个临时空 zvec（验证新代码能干净启动，不依赖本机索引）
if (-not $SkipCheck) {
    Step "自检：验证更新包内容可被应用启动"
    $venvPy = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path $venvPy)) {
        Write-Warning "未找到开发机 .venv（$venvPy），跳过自检（可用 -SkipCheck 关闭此提示）。"
    } else {
        $checkPy = Join-Path $stage 'selfcheck.py'
        if ($Type -eq 'kb') {
            $srcForCheck    = (Join-Path $ProjectRoot 'src')
            $zvecForCheck   = (Join-Path $stage 'data\zvec')
            $requireChunks  = '1'
        } else {
            $srcForCheck    = (Join-Path $stage 'src')
            $zvecForCheck   = (Join-Path $stage 'selfcheck-zvec')
            $requireChunks  = '0'
        }
        $code = @'
import os
from fastapi.testclient import TestClient
from aome_rag.main import create_app
app = create_app()
with TestClient(app) as c:
    r = c.get('/stats', headers={'X-User-Id': 'selfcheck'})
    assert r.status_code == 200, r.text
    n = r.json().get('n_chunks', 0)
    print('SELFCHECK n_chunks =', n)
    if os.environ.get('SELFCHECK_REQUIRE_CHUNKS') == '1':
        assert n > 0, '知识库索引为空，更新包无效'
print('SELFCHECK OK')
'@
        Set-Content -Path $checkPy -Value $code -Encoding utf8
        Push-Location $stage
        try {
            $env:PYTHONPATH             = $srcForCheck
            $env:ZVEC_PATH              = $zvecForCheck
            $env:SQLITE_PATH            = (Join-Path $stage 'sessions.db')
            $env:LOG_DIR                = (Join-Path $stage 'logs')
            $env:LOG_TO_FILE            = 'false'
            $env:SELFCHECK_REQUIRE_CHUNKS = $requireChunks
            & $venvPy $checkPy
            if ($LASTEXITCODE -ne 0) {
                Remove-Item $stage -Recurse -Force
                Die "自检失败：更新包内容无法启动应用，请勿交付此包。"
            }
        } finally {
            Remove-Item Env:PYTHONPATH, Env:ZVEC_PATH, Env:SQLITE_PATH, Env:LOG_DIR, Env:LOG_TO_FILE, Env:SELFCHECK_REQUIRE_CHUNKS -ErrorAction SilentlyContinue
            Pop-Location
        }
        Remove-Item $checkPy -Force -ErrorAction SilentlyContinue
        Remove-Item (Join-Path $stage 'selfcheck-zvec') -Recurse -Force -ErrorAction SilentlyContinue
        Remove-Item (Join-Path $stage 'sessions.db') -Force -ErrorAction SilentlyContinue
        Remove-Item (Join-Path $stage 'logs') -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zip -Force
Remove-Item $stage -Recurse -Force

Write-Host "更新包已生成: $zip" -ForegroundColor Green
Write-Host "下一步: 把此 zip 放进服务器 updates\ 文件夹，然后在服务器上双击「重启.bat」。" -ForegroundColor Yellow
