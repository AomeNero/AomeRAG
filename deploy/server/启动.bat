@echo off
rem ============================================================
rem  AomeRAG 局域网知识库服务器 · 一键启动
rem  小白双击本文件即可。首次运行会自动下载安装 Ollama 并拉取模型。
rem ============================================================
chcp 65001 >nul
setlocal

rem ---- 0) 请求管理员权限（装 Ollama / 防火墙 / 开机自启需要） ----
net session >nul 2>&1
if errorlevel 1 (
    echo.
    echo 需要管理员权限，正在弹出授权窗口，请点「是」。
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)
cd /d "%~dp0"

echo ============================================
echo    AomeRAG 局域网知识库服务器 - 一键启动
echo ============================================
echo.

rem ---- 1) Ollama 检查 / 下载 / 安装 ----
echo [1/5] 检查 Ollama ...
where ollama >nul 2>&1
if errorlevel 1 (
    echo       未检测到 Ollama，开始下载安装包（约 700MB，请耐心等待）...
    if not exist "%~dp0tools\OllamaSetup.exe" (
        powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://ollama.com/download/OllamaSetup.exe' -OutFile '%~dp0tools\OllamaSetup.exe' -UseBasicParsing"
    )
    if not exist "%~dp0tools\OllamaSetup.exe" (
        echo       下载失败！请检查网络后重新双击本文件。
        echo       如果仍失败，请手动打开浏览器访问 ollama.com 下载并安装。
        pause
        exit /b 1
    )
    echo       正在安装 Ollama（静默安装，请稍候）...
    start /wait "%~dp0tools\OllamaSetup.exe" /S
    rem 兜底：确保 Ollama 服务已启动
    net start Ollama >nul 2>&1
)

rem ---- 等待 Ollama 就绪 ----
echo       等待 Ollama 服务就绪 ...
set /a tries=0
:wait_ollama
ollama list >nul 2>&1
if not errorlevel 1 goto ollama_ready
set /a tries+=1
if %tries% geq 90 (
    echo       错误：Ollama 未能就绪。
    echo       请双击 tools\OllamaSetup.exe 手动完成安装后，再双击本文件。
    pause
    exit /b 1
)
timeout /t 2 /nobreak >nul
goto wait_ollama
:ollama_ready

rem ---- 2) bge-m3 模型检查 / 下载 ----
echo [2/5] 检查 embedding 模型 bge-m3 ...
ollama list | findstr /I /C:"bge-m3" >nul 2>&1
if errorlevel 1 (
    echo       未找到模型，开始下载 bge-m3（约 1.2GB，视网速 5-20 分钟）。
    echo       下载期间请勿关闭本窗口；若中断会自动重试。
    call :pull_bge3
    if errorlevel 1 (
        echo       模型下载多次失败。请检查网络后重新双击本文件。
        pause
        exit /b 1
    )
)

rem ---- 3) 防火墙放行 8000 ----
echo [3/5] 开放防火墙端口 8000 ...
netsh advfirewall firewall show rule name="AomeRAGService" >nul 2>&1
if errorlevel 1 (
    netsh advfirewall firewall add rule name="AomeRAGService" dir=in action=allow protocol=TCP localport=8000 >nul
)

rem ---- 4) 注册开机自启 ----
echo [4/5] 注册开机自启 ...
schtasks /query /tn "AomeRAGService" >nul 2>&1
if errorlevel 1 (
    schtasks /create /tn "AomeRAGService" /tr "\"%~dp0run_server.cmd\"" /sc onlogon /rl highest /f >nul
)

rem ---- 5) 停止旧实例并启动服务 ----
echo [5/5] 启动服务 ...
powershell -NoProfile -Command "$self=$PID; Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $self -and $_.CommandLine -like '*python*' -and $_.CommandLine -like '*aome_rag*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
start "AomeRAGService" /min "%~dp0run_server.cmd"

echo.
echo ============================================
echo    启动完成！
echo    本机访问:   http://localhost:8000
echo    局域网访问: http://本机IP:8000
echo ============================================
echo    本机 IPv4 地址如下（找 192.168.* 或 10.* 开头那行）：
ipconfig | findstr /I /C:"IPv4"
echo.
echo    - 服务窗口标题为 AomeRAGService，请勿关闭它。
echo    - 以后开机自动启动，无需再手动操作。
echo    - 知识库有更新时：把更新包放进 updates 文件夹，再双击「重启.bat」。
echo.
pause
exit /b

:pull_bge3
ollama pull bge-m3
if errorlevel 1 (
    echo       下载中断，5 秒后自动重试...
    timeout /t 5 /nobreak >nul
    goto pull_bge3
)
exit /b 0
