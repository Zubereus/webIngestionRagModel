@echo off
setlocal
cd /d "%~dp0"

if not defined GEMINI_API_KEY (
    for /f "tokens=2,*" %%A in ('reg query "HKCU\Environment" /v GEMINI_API_KEY 2^>nul') do (
        if "%%A"=="REG_SZ" set "GEMINI_API_KEY=%%B"
    )
)

where ngrok >nul 2>nul
if errorlevel 1 (
    echo ngrok was not found on PATH.
    echo Install it with: scoop install ngrok
    pause
    exit /b 1
)

ngrok config check >nul 2>nul
if errorlevel 1 (
    echo ngrok configuration is missing or invalid.
    echo Configure your token with: ngrok config add-authtoken YOUR_AUTHTOKEN
    echo Do not put your authentication token in this batch file.
    pause
    exit /b 1
)

curl --silent --fail http://127.0.0.1:8000/api/health >nul 2>nul
if errorlevel 1 (
    if not exist "%~dp0.venv\Scripts\python.exe" (
        echo Project Python environment not found at .venv\Scripts\python.exe
        pause
        exit /b 1
    )
    echo Starting WebRAG server on port 8000...
    start "WebRAG local server" /D "%~dp0" "%~dp0.venv\Scripts\python.exe" "%~dp0serve.py"
)

echo Waiting for WebRAG to become ready...
for /L %%i in (1,1,30) do (
    curl --silent --fail http://127.0.0.1:8000/api/health >nul 2>nul
    if not errorlevel 1 goto server_ready
    powershell.exe -NoProfile -Command "Start-Sleep -Seconds 1"
)

echo WebRAG did not become ready on http://127.0.0.1:8000.
echo Check the WebRAG server window for startup errors.
pause
exit /b 1

:server_ready
echo WebRAG is ready. Opening the ngrok tunnel in a separate window...
start "ngrok Tunnel" cmd /k "ngrok http 127.0.0.1:8000 --url=https://rearview-petunia-camera.ngrok-free.dev"
echo.
echo App server: http://127.0.0.1:8000
echo Public URL: https://rearview-petunia-camera.ngrok-free.dev
echo Keep the WebRAG and ngrok windows open while sharing the app.

endlocal
