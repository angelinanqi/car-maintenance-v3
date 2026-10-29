@echo off
setlocal

set "sdk=%ANDROID_HOME%"
if not defined sdk set "sdk=%ANDROID_SDK_ROOT%"
if not defined sdk set "sdk=%LOCALAPPDATA%\Android\Sdk"
set "emulator=%sdk%\emulator\emulator.exe"

if not exist "%emulator%" (
    echo Android Emulator not found. Install it in Android Studio or set ANDROID_HOME.
    pause
    exit /b 1
)

set "avd=%~1"
if not defined avd (
    for /f "delims=" %%A in ('""%emulator%" -list-avds"') do (
        if not defined avd set "avd=%%A"
    )
)

if not defined avd (
    echo No Android virtual devices found. Create one in Android Studio Device Manager.
    pause
    exit /b 1
)

echo Starting emulator: %avd%
"%emulator%" -avd "%avd%"
set "result=%errorlevel%"
if not "%result%"=="0" pause
exit /b %result%
