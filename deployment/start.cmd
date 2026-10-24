@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 场景审核工作台：http://127.0.0.1:8765
start "" http://127.0.0.1:8765
python\python.exe app\serve.py --data-dir "%~dp0data"
pause
