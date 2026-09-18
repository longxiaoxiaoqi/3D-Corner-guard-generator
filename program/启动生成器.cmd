@echo off
cd /d "%~dp0"
python corner_guard.py --gui
if errorlevel 1 pause
