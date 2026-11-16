@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Instalando dependencias do DDTank Helper...
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Falha ao instalar. Verifique se Python 3.10+ esta instalado e adicionado ao PATH.
  pause
  exit /b 1
)
echo.
echo Dependencias instaladas.
echo IMPORTANTE: instale o Tesseract OCR para Windows e, se necessario, configure o caminho no pytesseract.
echo https://github.com/UB-Mannheim/tesseract/wiki
pause
