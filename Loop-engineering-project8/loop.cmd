@echo off
REM Loop Engineering Practice Project 8 - Entry Point
REM Runs exactly ONE pass of the six-part loop and propagates exit code.

cd /d "%~dp0"
python -m src.loop
exit /b %errorlevel%