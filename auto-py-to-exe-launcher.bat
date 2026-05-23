@echo off
chcp 65001 >nul
echo ========================================
echo Python to EXE Converter
echo ========================================
echo.

REM 현재 가상환경 확인
if defined VIRTUAL_ENV (
    echo 가상환경이 이미 활성화되어 있습니다: %VIRTUAL_ENV%
) else (
    echo 가상환경을 찾는 중...
    
    REM .venv 폴더 확인
    if exist ".venv\Scripts\activate.bat" (
        echo .venv 가상환경을 활성화합니다...
        call .venv\Scripts\activate.bat
    ) else if exist ".venv1\Scripts\activate.bat" (
        echo .venv1 가상환경을 활성화합니다...
        call .venv1\Scripts\activate.bat
    ) else if exist ".venv2\Scripts\activate.bat" (
        echo .venv2 가상환경을 활성화합니다...
        call .venv2\Scripts\activate.bat
    ) else if exist "myenv\Scripts\activate.bat" (
        echo myenv 가상환경을 활성화합니다...
        call myenv\Scripts\activate.bat
    ) else (
        echo 가상환경을 찾을 수 없습니다. 시스템 Python을 사용합니다.
    )
)

echo.
echo auto-py-to-exe가 설치되어 있는지 확인 중...
python -m pip show auto-py-to-exe >nul 2>&1

if %errorlevel% neq 0 (
    echo auto-py-to-exe가 설치되어 있지 않습니다.
    echo.
    echo auto-py-to-exe를 자동으로 설치합니다...
    python -m pip install auto-py-to-exe
    
    if %errorlevel% neq 0 (
        echo.
        echo 설치에 실패했습니다.
        pause
        exit /b 1
    )
    
    echo.
    echo 설치가 완료되었습니다!
) else (
    echo auto-py-to-exe가 이미 설치되어 있습니다.
)

echo.
echo auto-py-to-exe를 실행합니다...
echo 브라우저가 자동으로 열립니다.
echo.
python -m auto_py_to_exe

if %errorlevel% neq 0 (
    echo.
    echo auto-py-to-exe 실행에 실패했습니다.
    pause
    exit /b 1
)

echo.
echo auto-py-to-exe가 종료되었습니다.
pause