@echo off
chcp 65001 >nul
cd /d "%~dp0"
python\python.exe -c "import deepagents,fastapi,uvicorn,jsonschema; print('离线运行依赖正常')"
if errorlevel 1 goto end
python\python.exe -m pytest app\tests -q
:end
pause
