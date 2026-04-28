@echo off
set "PROJECT_DIR=C:\Users\itaik\Desktop\Master Thesis 2026-2027 CodeBase"

echo Starting Lexi project...

start "Lexi Server" cmd /k "cd /d "%PROJECT_DIR%\Lexi\server" && npm run dev"

start "Lexi Client" cmd /k "cd /d "%PROJECT_DIR%\Lexi\client" && npm start"

@REM start "Android Emulator" cmd /k ""%LOCALAPPDATA%\Android\Sdk\emulator\emulator.exe" -avd Medium_Phone"

timeout /t 20

"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe" wait-for-device
"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe" reverse tcp:3000 tcp:3000
"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe" reverse tcp:5000 tcp:5000

echo Emulator ports connected!
pause