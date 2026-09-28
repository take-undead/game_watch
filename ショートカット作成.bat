@echo off
rem デスクトップとこのフォルダに、アイコン付きのショートカット「GnW改造ツール」を作成します
cd /d "%~dp0"
where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw -m gnwtool.shortcut
    exit /b 0
)
python -m gnwtool.shortcut
if errorlevel 1 pause
