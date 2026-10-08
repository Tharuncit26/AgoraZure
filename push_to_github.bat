@echo off
setlocal
echo ===================================================
echo     AgoraZure - 1-Click Push to GitHub Helper
echo ===================================================
echo.

set "GIT_CMD=git"
where git >nul 2>nul
if %errorlevel% neq 0 (
    set "GIT_CMD=%USERPROFILE%\.mingit\cmd\git.exe"
)

echo Checking Git...
"%GIT_CMD%" --version
if %errorlevel% neq 0 (
    echo [ERROR] Git could not be found.
    pause
    exit /b 1
)

echo.
echo Step 1: Open https://github.com/new in your browser
echo Step 2: Name your repository (e.g. agorazure), and click "Create repository"
echo Step 3: Copy the repository URL (e.g. https://github.com/your-username/agorazure.git)
echo.
set /p REPO_URL="Paste your GitHub repository link here and press Enter: "

if "%REPO_URL%"=="" (
    echo [ERROR] No URL entered. Exiting.
    pause
    exit /b 1
)

echo.
echo Linking repository to %REPO_URL%...
"%GIT_CMD%" remote remove origin >nul 2>nul
"%GIT_CMD%" remote add origin %REPO_URL%
"%GIT_CMD%" branch -M main

echo.
echo Pushing your files to GitHub...
"%GIT_CMD%" push -u origin main

if %errorlevel% equ 0 (
    echo.
    echo ===================================================
    echo  [SUCCESS] All files are now on GitHub!
    echo  Next: Open https://vercel.com/new and click Import!
    echo ===================================================
) else (
    echo.
    echo If GitHub asks to sign in, click 'Sign in with your browser' or use a Token.
)

echo.
pause
