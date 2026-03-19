@echo off
echo === Build OrganizzatoreFile.exe ===
echo.

REM Verifica che pyinstaller sia installato
pyinstaller --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERRORE: PyInstaller non trovato.
    echo Esegui prima: pip install -r requirements.txt
    pause
    exit /b 1
)

pyinstaller ^
    --onefile ^
    --windowed ^
    --name "OrganizzatoreFile" ^
    --collect-all ttkbootstrap ^
    app\FileOrganizer.py

echo.
if %errorlevel% == 0 (
    echo ============================================
    echo  SUCCESSO: dist\OrganizzatoreFile.exe
    echo  Copia il file .exe ai colleghi: non serve
    echo  installare Python sul loro PC.
    echo ============================================
) else (
    echo ERRORE: build fallita con codice %errorlevel%
)
pause
