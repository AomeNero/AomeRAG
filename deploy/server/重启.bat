@echo off
rem ============================================================
rem  AomeRAG · 重启服务 / 应用更新包
rem  知识库有更新包时，把 zip 放进 updates 文件夹，双击本文件即可。
rem ============================================================
chcp 65001 >nul
setlocal

net session >nul 2>&1
if errorlevel 1 (
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)
cd /d "%~dp0"

echo 正在停止旧服务...
powershell -NoProfile -Command "$self=$PID; Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $self -and $_.CommandLine -like '*python*' -and $_.CommandLine -like '*aome_rag*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
timeout /t 2 /nobreak >nul

echo 应用更新包（updates\*.zip → 覆盖到 app\）...
if exist "%~dp0updates\*.zip" (
    if not exist "%~dp0updates\applied" mkdir "%~dp0updates\applied"
    for %%f in ("%~dp0updates\*.zip") do (
        echo   应用: %%~nxf
        powershell -NoProfile -Command "Expand-Archive -LiteralPath '%%f' -DestinationPath '%~dp0app' -Force"
        move /Y "%%f" "%~dp0updates\applied\%%~nxf" >nul 2>&1
    )
) else (
    echo   无更新包，直接重启。
)

echo 启动服务...
start "AomeRAGService" /min "%~dp0run_server.cmd"

echo.
echo 完成！服务已重启。本机访问 http://localhost:8000
echo.
pause
exit /b
