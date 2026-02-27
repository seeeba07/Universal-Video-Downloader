@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

if not exist VERSION.txt (
	echo 1.2>VERSION.txt
)

echo Build mode: using current VERSION.txt value.

set "APP_VERSION="
set /p APP_VERSION=<VERSION.txt

if "%APP_VERSION%"=="" set "APP_VERSION=unknown"

echo Version: %APP_VERSION%

echo Cleaning previous outputs...
if exist build rmdir /s /q build
if exist dist\media_downloader rmdir /s /q dist\media_downloader
if exist dist\media_downloader_portable_*.zip del /q dist\media_downloader_portable_*.zip
if exist dist\media_downloader_setup_*.exe del /q dist\media_downloader_setup_*.exe
if exist dist\media_downloader_*.exe del /q dist\media_downloader_*.exe

echo Building portable app (PyInstaller onedir)...
echo.
set "PYI_EXE=pyinstaller"
if exist ".venv\Scripts\pyinstaller.exe" set "PYI_EXE=.venv\Scripts\pyinstaller.exe"
"%PYI_EXE%" --clean --noconfirm mdl.spec
if errorlevel 1 goto :build_error

echo.
echo Creating portable ZIP...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'dist\\media_downloader\\*' -DestinationPath 'dist\\media_downloader_portable_%APP_VERSION%.zip' -Force"
if errorlevel 1 goto :build_error

echo.
echo Building installer (Inno Setup)...
set "ISCC_EXE="
for %%I in (iscc.exe) do set "ISCC_EXE=%%~$PATH:I"

if not defined ISCC_EXE if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC_EXE=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not defined ISCC_EXE if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set "ISCC_EXE=C:\Program Files\Inno Setup 6\ISCC.exe"

if not defined ISCC_EXE (
	echo.
	echo [WARNING] Inno Setup was not found. Portable build is ready, installer was skipped.
	echo Install Inno Setup from https://jrsoftware.org/isinfo.php and rerun this script.
	goto :done
)

"%ISCC_EXE%" /DAppVersion=%APP_VERSION% installer.iss
if errorlevel 1 goto :build_error

:done
echo.
echo Finalizing dist outputs...
if exist dist\media_downloader.exe del /q dist\media_downloader.exe
if exist dist\media_downloader rmdir /s /q dist\media_downloader

echo.
echo ========================================================
echo DONE!
echo Portable ZIP:    dist\media_downloader_portable_%APP_VERSION%.zip
echo Installer:    dist\media_downloader_setup_%APP_VERSION%.exe
echo ========================================================
pause
exit /b 0

:build_error
echo.
echo ========================================================
echo BUILD FAILED. Check messages above.
echo ========================================================
pause
exit /b 1