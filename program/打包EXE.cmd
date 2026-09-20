@echo off
cd /d "%~dp0"
python -m venv .build-venv
if errorlevel 1 goto fail
".build-venv\Scripts\python.exe" -m pip install -r requirements-build.txt
if errorlevel 1 goto fail
".build-venv\Scripts\python.exe" -m PyInstaller --noconfirm CoverGenerator.spec
if errorlevel 1 goto fail
echo Built: dist\CoverGenerator.exe
pause
exit /b 0
:fail
echo Build failed. Check the messages above.
pause
exit /b 1
