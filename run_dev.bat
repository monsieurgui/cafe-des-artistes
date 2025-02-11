@echo off
setlocal

REM Set environment variables
set "BOT_ENV=development"
set "PYTHONPATH=%~dp0"

REM Set FFmpeg path to local bin directory
set "FFMPEG_PATH=%~dp0bin\ffmpeg.exe"

REM Check if FFmpeg exists
if not exist "%FFMPEG_PATH%" (
    echo FFmpeg not found at %FFMPEG_PATH%
    echo Please ensure FFmpeg is installed in the bin directory
    pause
    exit /b 1
)

REM Run the bot
python src/main.py
endlocal 