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

.NOTES
  用法：
    powershell -ExecutionPolicy Bypass -File deploy\build_update.ps1 -Type kb
    powershell -ExecutionPolicy Bypass -File deploy\build_update.ps1 -Type app
#>
# 手动解析参数（同 build_bundle.ps1，规避 PS 5.1 的 param 块 + 位置参数绑定 bug）
$ProjectRoot = ''
$Type        = 'kb'
$OutDir      = ''
for ($i = 0; $i -lt $args.Count; $i++) {
    switch ($args[$i]) {
        '-ProjectRoot' { $i++; if ($i -lt $args.Count) { $ProjectRoot = $args[$i] } }
        '-Type'        { $i++; if ($i -lt $args.Count) { $Type = $args[$i] } }
        '-OutDir'      { $i++; if ($i -lt $args.Count) { $OutDir = $args[$i] } }
    }
}
if (-not $ProjectRoot) { $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path }
if (-not $OutDir)      { $OutDir = Join-Path $PSScriptRoot 'out' }
if ($Type -notin @('kb', 'app')) { Write-Host "!! -Type 仅支持 kb / app"; exit 1 }

$ErrorActionPreference = 'Stop'
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

Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zip -Force
Remove-Item $stage -Recurse -Force

Write-Host "更新包已生成: $zip" -ForegroundColor Green
Write-Host "下一步: 把此 zip 放进服务器 updates\ 文件夹，然后在服务器上双击「重启.bat」。" -ForegroundColor Yellow
