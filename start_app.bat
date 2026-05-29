@echo off
title Sequential Bulk Image Downloader
echo Starting Sequential Bulk Image Downloader...
python main.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo Application exited with an error.
    pause
)
