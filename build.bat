@echo off
chcp 65001 >nul
echo ==============================
echo  iOS 开发者设置工具 - 打包脚本
echo ==============================
echo.

REM 查找可用的 Python 命令（py > python > python3）
set PYTHON=
where py >nul 2>&1 && set PYTHON=py && goto :found
where python >nul 2>&1 && set PYTHON=python && goto :found
where python3 >nul 2>&1 && set PYTHON=python3 && goto :found

echo [错误] 未找到 Python！
echo.
echo 请先安装 Python 3.10+：
echo   1. 访问 https://www.python.org/downloads/
echo   2. 下载并安装，安装时务必勾选 "Add Python to PATH"
echo   3. 安装完成后重新运行此脚本
echo.
pause
exit /b 1

:found
echo 使用 Python: %PYTHON%
%PYTHON% --version
echo.

echo [1/4] 安装打包依赖...
%PYTHON% -m pip install pyinstaller pymobiledevice3 PySide6 -q
if errorlevel 1 (
    echo [错误] 依赖安装失败！请检查网络连接。
    pause
    exit /b 1
)

echo [2/4] 准备 DDI 镜像数据...
%PYTHON% prepare_ddi.py
if errorlevel 1 (
    echo [错误] DDI 数据准备失败！
    pause
    exit /b 1
)

echo [3/4] 开始打包（含内置镜像，约需几分钟）...
%PYTHON% -m PyInstaller build.spec --clean --noconfirm
if errorlevel 1 (
    echo [错误] 打包失败！
    pause
    exit /b 1
)

echo.
echo ==============================
echo  [4/4] 打包完成!
echo  输出文件: dist\iOS开发者设置工具.exe
echo ==============================
echo.
pause
