@echo off
REM ────────────────────────────────────────────────────────────────────
REM Clicky Windows — one-click build script
REM
REM Produces:  dist\Clicky\Clicky.exe   (portable folder)
REM            Setup-Clicky.exe         (if Inno Setup is installed)
REM
REM Usage:  build.bat           ← builds portable folder only
REM         build.bat installer ← also builds Setup-Clicky.exe
REM ────────────────────────────────────────────────────────────────────

setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ================================================================
echo   Clicky for Windows — Build
echo ================================================================
echo.

REM ── 1. Sanity check Python ─────────────────────────────────────────
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found on PATH. Install Python 3.11+ first.
    exit /b 1
)

REM ── 2. Install build deps if missing ───────────────────────────────
echo [1/4] Checking build dependencies...
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo     Installing PyInstaller...
    python -m pip install --quiet --upgrade pyinstaller
)
python -c "import PyQt6" 2>nul
if errorlevel 1 (
    echo     Installing project requirements...
    python -m pip install --quiet -r requirements.txt
)

REM ── 2b. Generate icon if missing ───────────────────────────────────
if not exist "assets\icon.ico" (
    echo     Generating default icon...
    python "assets\make_icon.py"
)

REM ── 3. Clean old build ─────────────────────────────────────────────
echo [2/4] Cleaning old build...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM ── 4. Run PyInstaller ─────────────────────────────────────────────
echo [3/4] Building with PyInstaller (this takes 2-5 min)...
python -m PyInstaller clicky.spec --clean --noconfirm
if errorlevel 1 (
    echo.
    echo [ERROR] Build failed. Check the output above.
    exit /b 1
)

REM ── 5. Copy .env.example and LICENSE into the dist folder ─────────
echo [4/4] Bundling docs and env template...
copy /y ".env.example" "dist\Clicky\.env.example" >nul
if exist ".env" copy /y ".env" "dist\Clicky\.env" >nul
copy /y "LICENSE"       "dist\Clicky\LICENSE"      >nul
copy /y "HOW-TO-USE.txt"       "dist\Clicky\HOW-TO-USE.txt"       >nul
copy /y "HOW-TO-USE-中文.txt"  "dist\Clicky\HOW-TO-USE-中文.txt"  >nul

REM ── 6. Create upload zip for floweralice.me ───────────────────────
echo [5/5] Creating clicky-windows-artists.zip for website upload...
if exist clicky-windows-artists.zip del /f /q clicky-windows-artists.zip
powershell -NoProfile -Command "Compress-Archive -Path 'dist\Clicky' -DestinationPath 'clicky-windows-artists.zip' -Force"
if errorlevel 1 (
    echo [WARN] Could not create clicky-windows-artists.zip — upload dist\Clicky manually.
) else (
    echo     Upload clicky-windows-artists.zip to:
    echo     www.floweralice.me/clicky/download/clicky-windows-artists.zip
)

echo.
echo ================================================================
echo   Portable build complete!
echo   Run:  dist\Clicky\Clicky.exe
echo   Zip:  clicky-windows-artists.zip  ^(upload to website^)
echo ================================================================
echo.

REM ── 7. Optional: build Inno Setup installer ────────────────────────
if /i "%1"=="installer" (
    echo Building Inno Setup installer...
    where iscc >nul 2>&1
    if errorlevel 1 (
        set "ISCC=C:\Program Files ^(x86^)\Inno Setup 6\ISCC.exe"
        if not exist "!ISCC!" (
            echo [WARN] Inno Setup not found. Install from https://jrsoftware.org/isdl.php
            echo        Then re-run:  build.bat installer
            exit /b 0
        )
        "!ISCC!" installer.iss
    ) else (
        iscc installer.iss
    )
    echo.
    echo Installer: dist\Setup-Clicky.exe
)

endlocal
