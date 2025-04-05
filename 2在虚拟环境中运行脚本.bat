@echo off
echo.
echo 正在运行 main.py...
echo.

:: 激活虚拟环境
call myenv\Scripts\activate

:: 在虚拟环境中运行 main.py
start /min cmd /c "python main.py && pause"

:: 等待 2 秒
timeout /t 2