@echo off
rem ============================================================
rem  AomeRAG 服务启动器（供「启动.bat」「重启.bat」和开机自启调用）
rem  运行的是 app 目录里的源码 + 包内便携 Python，监听 0.0.0.0:8000。
rem ============================================================
title AomeRAGService
cd /d "%~dp0"

rem 等 Ollama 就绪（最多 60 秒），避免开机时服务先于 Ollama 启动
set /a tries=0
:wait
ollama list >nul 2>&1
if not errorlevel 1 goto ready
set /a tries+=1
if %tries% geq 30 goto ready
timeout /t 2 /nobreak >nul
goto wait
:ready

cd /d "%~dp0app"
set "PYTHONPATH=%~dp0app\src"
"%~dp0runtime\python\python.exe" -m aome_rag --host 0.0.0.0 --port 8000
