@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title 安装 Python 3.13 到 D 盘（第 3 周环境准备）

echo ============================================================
echo   本脚本会：
echo     1. 下载 Python 3.13.9 Windows 安装包（优先国内镜像）
echo     2. 静默安装到  D:\Tools\Python313   （不占 C 盘）
echo     3. 把 Python 与 Scripts 目录写入当前用户 PATH
echo     4. 安装后自动 pip install -r requirements.txt
echo ============================================================
echo.

set "PY_VER=3.13.9"
set "INSTALL_DIR=D:\Tools\Python313"
set "EXE=%TEMP%\python-%PY_VER%-amd64.exe"

where python >nul 2>nul
if %errorlevel%==0 (
    echo [提示] 当前 PATH 里已经有 python：
    python --version
    echo.
    set /p GOON=仍然继续安装? (Y/N):
    if /i not "!GOON!"=="Y" goto :end
)

if not exist "%EXE%" (
    echo [1/4] 下载安装包...
    curl.exe -L --retry 3 --connect-timeout 20 -o "%EXE%" "https://registry.npmmirror.com/-/binary/python/%PY_VER%/python-%PY_VER%-amd64.exe"
    if not exist "%EXE%" (
        echo     国内镜像失败，改用官方源...
        curl.exe -L --retry 3 --connect-timeout 20 -o "%EXE%" "https://www.python.org/ftp/python/%PY_VER%/python-%PY_VER%-amd64.exe"
    )
) else (
    echo [1/4] 安装包已存在，跳过下载
)

if not exist "%EXE%" (
    echo [X] 下载失败，请检查网络后重试，或手动下载：
    echo     https://www.python.org/downloads/windows/
    goto :end
)

echo [2/4] 静默安装到 %INSTALL_DIR% ...
if not exist "D:\Tools" mkdir "D:\Tools"
"%EXE%" /quiet InstallAllUsers=0 TargetDir=%INSTALL_DIR% PrependPath=1 Include_pip=1 Include_launcher=0 Include_test=0 Shortcuts=0

echo [3/4] 校验安装结果...
if not exist "%INSTALL_DIR%\python.exe" (
    echo [X] 安装似乎失败，未找到 %INSTALL_DIR%\python.exe
    echo     可改用手动安装：运行安装包，勾选 Add python.exe to PATH
    goto :end
)
"%INSTALL_DIR%\python.exe" --version

echo [4/4] 安装依赖...
cd /d "%~dp0python-lab"
"%INSTALL_DIR%\python.exe" -m pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

echo.
echo ============================================================
echo   完成。请【关闭本窗口并重新打开 PowerShell】后再执行：
echo       python --version
echo       cd /d %~dp0python-lab ^&^& python 01_env_check.py
echo ============================================================

:end
echo.
pause
