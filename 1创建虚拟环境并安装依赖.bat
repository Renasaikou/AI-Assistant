@echo off
echo.
echo 正在安装所需的Python包...
echo.

:: 检查是否安装了Python和pip
python -m pip --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo 未检测到Python或pip，请确保已正确安装Python并将其添加到系统环境变量中。
    pause
    exit /b 1
)

:: 检查Python版本是否为3.11.0rc1
for /f "tokens=*" %%i in ('python --version') do set pyversion=%%i
echo 检测到的Python版本为：%pyversion%
echo.
if not "%pyversion%"=="Python 3.11.0rc1" (
    echo 警告：当前Python版本不是3.11.0rc1。请确保使用Python 3.11.0rc1以避免兼容性问题。
    pause
    exit /b 1
)

:: 创建虚拟环境
echo 正在创建虚拟环境...
python -m venv myenv
if %ERRORLEVEL% neq 0 (
    echo 创建虚拟环境失败，请检查Python版本和权限。
    pause
    exit /b 1
)

:: 激活虚拟环境
echo 激活虚拟环境...
call myenv\Scripts\activate
if %ERRORLEVEL% neq 0 (
    echo 激活虚拟环境失败，请检查路径是否正确。
    pause
    exit /b 1
)

:: 设置默认使用阿里源
set PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/

:: 安装依赖
echo 正在安装依赖...
pip install opencc requests wave pyaudio torch numpy faster-whisper edge-tts pydub playsound pillow zhipuai
if %ERRORLEVEL% neq 0 (
    echo 安装依赖失败，请检查网络连接或依赖包名称。
    pause
    exit /b 1
)

echo.
echo 所有包已安装完成！
pause
exit /b 0