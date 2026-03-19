@echo off
chcp 65001 >nul 2>&1
title Instalador - Erome Downloader

echo.
echo  ╔═══════════════════════════════════════╗
echo  ║     EROME DOWNLOADER - Instalador     ║
echo  ╚═══════════════════════════════════════╝
echo.

set "INSTALL_DIR=%LocalAppData%\EromeDownloader"
set "EXE_NAME=EromeDownloader.exe"
set "SCRIPT_DIR=%~dp0"

echo  [1/3] Criando pasta de instalacao...
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

echo  [2/3] Copiando arquivos...
copy /Y "%SCRIPT_DIR%%EXE_NAME%" "%INSTALL_DIR%\%EXE_NAME%" >nul
if exist "%SCRIPT_DIR%icon.ico" copy /Y "%SCRIPT_DIR%icon.ico" "%INSTALL_DIR%\icon.ico" >nul

echo  [3/3] Criando atalho na Area de Trabalho...
set "DESKTOP=%UserProfile%\Desktop"
set "SHORTCUT=%DESKTOP%\Erome Downloader.lnk"

powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT%'); $s.TargetPath = '%INSTALL_DIR%\%EXE_NAME%'; $s.WorkingDirectory = '%INSTALL_DIR%'; if (Test-Path '%INSTALL_DIR%\icon.ico') { $s.IconLocation = '%INSTALL_DIR%\icon.ico' }; $s.Description = 'Erome Downloader'; $s.Save()"

echo.
echo  ✓ Instalacao concluida!
echo.
echo  Programa instalado em: %INSTALL_DIR%
echo  Atalho criado na Area de Trabalho.
echo.
echo  Voce pode deletar esta pasta do instalador agora.
echo.
pause
