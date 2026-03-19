"""
Auto-updater via GitHub Releases.

Flow:
  1. App starts -> check latest release on GitHub
  2. Compare version with current
  3. If newer: show dialog -> download new exe -> replace -> restart
"""

import asyncio
import logging
import os
import sys
import subprocess
import tempfile
from typing import Callable

import aiohttp

from src.utils.config import APP_VERSION, CONNECT_TIMEOUT

logger = logging.getLogger(__name__)

GITHUB_OWNER = "Pasqualotty"
GITHUB_REPO = "eromedownloader"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
ASSET_NAME = "EromeDownloader.exe"


def _get_exe_path() -> str | None:
    if getattr(sys, 'frozen', False):
        return sys.executable
    return None


def _version_tuple(v: str) -> tuple[int, ...]:
    v = v.lstrip("vV").strip()
    parts = []
    for p in v.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def is_newer(remote: str, local: str) -> bool:
    return _version_tuple(remote) > _version_tuple(local)


async def check_for_update(
    on_status: Callable[[str], None] | None = None,
) -> dict | None:
    """
    Returns dict with keys: version, download_url, size, notes
    or None if no update available.
    """
    status = on_status or (lambda m: None)

    try:
        timeout = aiohttp.ClientTimeout(total=15, connect=CONNECT_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "EromeDownloader-Updater",
            }
            async with session.get(GITHUB_API, headers=headers) as resp:
                if resp.status == 404:
                    status("Repositorio de updates nao encontrado.")
                    return None
                if resp.status == 403:
                    status("Rate limit do GitHub atingido, tente mais tarde.")
                    return None
                if resp.status != 200:
                    return None

                data = await resp.json()

        tag = data.get("tag_name", "")
        if not tag:
            return None

        if not is_newer(tag, APP_VERSION):
            return None

        download_url = None
        size = 0
        for asset in data.get("assets", []):
            if asset.get("name", "") == ASSET_NAME:
                download_url = asset.get("browser_download_url", "")
                size = asset.get("size", 0)
                break

        if not download_url:
            status(f"Versao {tag} encontrada, mas sem executavel para download.")
            return None

        notes = data.get("body", "")

        return {
            "version": tag.lstrip("vV"),
            "download_url": download_url,
            "size": size,
            "notes": notes,
        }

    except Exception as e:
        logger.warning(f"Erro ao verificar updates: {e}")
        return None


async def download_update(
    download_url: str,
    on_progress: Callable[[float], None] | None = None,
    on_status: Callable[[str], None] | None = None,
) -> str | None:
    """
    Downloads new exe to temp file. Returns path to downloaded file.
    """
    status = on_status or (lambda m: None)
    progress = on_progress or (lambda p: None)

    exe_path = _get_exe_path()
    if not exe_path:
        status("Update so funciona no executavel (.exe)")
        return None

    try:
        timeout = aiohttp.ClientTimeout(total=600, connect=CONNECT_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(download_url) as resp:
                if resp.status != 200:
                    status(f"Erro ao baixar update: HTTP {resp.status}")
                    return None

                total = resp.content_length or 0
                downloaded = 0

                tmp_dir = os.path.dirname(exe_path)
                tmp_fd, tmp_path = tempfile.mkstemp(
                    suffix=".exe.update",
                    dir=tmp_dir,
                )
                os.close(tmp_fd)

                with open(tmp_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(131072):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            progress(downloaded / total)

        return tmp_path

    except Exception as e:
        status(f"Erro durante download do update: {e}")
        logger.warning(f"Update download failed: {e}")
        return None


def apply_update_and_restart(tmp_path: str):
    """
    Replaces current exe with downloaded one and restarts.
    Uses a batch script because we can't replace a running exe directly on Windows.
    """
    exe_path = _get_exe_path()
    if not exe_path:
        return

    bat_path = exe_path + ".update.bat"

    bat_content = f'''@echo off
chcp 65001 >nul 2>&1
echo Atualizando EromeDownloader...
timeout /t 2 /nobreak >nul
del /F "{exe_path}"
move /Y "{tmp_path}" "{exe_path}"
start "" "{exe_path}"
del /F "%~f0"
'''

    with open(bat_path, "w", encoding="utf-8") as f:
        f.write(bat_content)

    subprocess.Popen(
        ["cmd.exe", "/c", bat_path],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )

    sys.exit(0)
