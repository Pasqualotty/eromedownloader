@echo off
chcp 65001 >nul 2>&1
title Desinstalador - Erome Downloader

echo.
echo  ╔═══════════════════════════════════════╗
echo  ║   EROME DOWNLOADER - Desinstalar      ║
echo  ╚═══════════════════════════════════════╝
echo.

set "INSTALL_DIR=%LocalAppData%\EromeDownloader"
set "SHORTCUT=%UserProfile%\Desktop\Erome Downloader.lnk"
set "DATA_DIR=%UserProfile%\.eromedl"

echo  Isso vai remover o Erome Downloader do seu computador.
echo.
choice /C SN /M "  Deseja continuar? (S/N)"
if errorlevel 2 goto :cancel

echo.
echo  [1/3] Removendo atalho...
if exist "%SHORTCUT%" del /F "%SHORTCUT%"

echo  [2/3] Removendo programa...
if exist "%INSTALL_DIR%" rmdir /S /Q "%INSTALL_DIR%"

echo  [3/3] Remover configuracoes salvas?
choice /C SN /M "         Apagar configuracoes? (S/N)"
if errorlevel 2 goto :done
if exist "%DATA_DIR%" rmdir /S /Q "%DATA_DIR%"

:done
echo.
echo  ✓ Desinstalacao concluida!
echo.
pause
exit /b

:cancel
echo.
echo  Cancelado.
pause
