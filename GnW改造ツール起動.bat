@echo off
rem G&W 改造ツールを起動します（コンソール画面は表示しません）
cd /d "%~dp0"
where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw -m gnwtool
    exit /b 0
)
where python >nul 2>nul
if %errorlevel%==0 (
    python -m gnwtool
    if errorlevel 1 pause
    exit /b 0
)
echo Python が見つかりません。https://www.python.org/ から Python 3.9 以上をインストールしてください。
pause
