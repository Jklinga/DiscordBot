@echo off
rem Builds PurgeBot.exe and puts it in this folder.
rem The icon comes from purgeBot.png (via assets\make_icons.py).
cd /d "%~dp0"

python -m pip install --upgrade pyinstaller pillow || goto :error
python assets\make_icons.py || goto :error

python -m PyInstaller --noconfirm --onefile --windowed --name PurgeBot ^
    --icon assets\purgebot.ico ^
    --add-data "assets\icon.png;assets" ^
    --add-data "assets\header.png;assets" ^
    --add-data "assets\purgebot.ico;assets" ^
    PurgeBot.pyw || goto :error

copy /y dist\PurgeBot.exe PurgeBot.exe >nul
echo.
echo Done! PurgeBot.exe is in %~dp0
echo It keeps token.txt, settings.json and Members.json in the same folder as itself.
pause
exit /b 0

:error
echo.
echo Build failed, see the messages above.
pause
exit /b 1
