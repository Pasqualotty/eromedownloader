import asyncio
import logging
import os
from typing import Callable

import aiohttp
import aiofiles

from src.utils.config import (
    CHUNK_SIZE, MAX_RETRIES, RETRY_BASE_DELAY, DOWNLOAD_HEADERS,
    DOWNLOAD_TIMEOUT, CONNECT_TIMEOUT,
)
from src.core.models import (
    MediaItem, MediaType, DownloadResult, DownloadStats, DownloadOptions,
)

logger = logging.getLogger(__name__)


class DownloadManager:
    def __init__(
        self,
        options: DownloadOptions,
        on_progress: Callable[[DownloadStats], None] | None = None,
        on_result: Callable[[DownloadResult], None] | None = None,
        on_status: Callable[[str], None] | None = None,
        cancel_event: asyncio.Event | None = None,
    ):
        self.options = options
        self.on_progress = on_progress or (lambda s: None)
        self.on_result = on_result or (lambda r: None)
        self.on_status = on_status or (lambda m: None)
        self.cancel_event = cancel_event or asyncio.Event()
        self.stats = DownloadStats()
        self._semaphore: asyncio.Semaphore | None = None

    async def download_all(self, items: list[MediaItem]):
        self.stats = DownloadStats(total=len(items))
        self._semaphore = asyncio.Semaphore(self.options.workers)
        self.on_progress(self.stats)

        timeout = aiohttp.ClientTimeout(
            total=DOWNLOAD_TIMEOUT,
            connect=CONNECT_TIMEOUT,
            sock_read=60,
        )
        connector = aiohttp.TCPConnector(
            limit=self.options.workers * 3,
            limit_per_host=self.options.workers * 2,
            ttl_dns_cache=600,
            enable_cleanup_closed=True,
            force_close=False,
            keepalive_timeout=30,
        )
        async with aiohttp.ClientSession(
            headers=DOWNLOAD_HEADERS,
            connector=connector,
            timeout=timeout,
        ) as session:
            tasks = [self._download_item(session, item) for item in items]
            await asyncio.gather(*tasks)

        self.on_status(
            f"Download finalizado: {self.stats.completed} OK, "
            f"{self.stats.failed} falhas, {self.stats.skipped} ignorados"
        )

    async def _download_item(self, session: aiohttp.ClientSession, item: MediaItem):
        if self.cancel_event.is_set():
            return

        async with self._semaphore:
            if self.cancel_event.is_set():
                return

            dest_dir = self._get_dest_dir(item)
            os.makedirs(dest_dir, exist_ok=True)
            dest_path = os.path.join(dest_dir, item.filename)
            part_path = dest_path + ".part"

            if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
                result = DownloadResult(item=item, success=True, skipped=True)
                self.stats.completed += 1
                self.stats.skipped += 1
                self.on_result(result)
                self.on_progress(self.stats)
                return

            for attempt in range(MAX_RETRIES):
                if self.cancel_event.is_set():
                    return
                try:
                    file_size = await self._do_download(session, item, part_path)
                    os.rename(part_path, dest_path)

                    result = DownloadResult(item=item, success=True, file_size=file_size)
                    self.stats.completed += 1
                    self.stats.total_bytes += file_size
                    self.on_result(result)
                    self.on_progress(self.stats)
                    return

                except Exception as e:
                    if os.path.exists(part_path):
                        try:
                            os.remove(part_path)
                        except OSError:
                            pass

                    if attempt < MAX_RETRIES - 1:
                        delay = RETRY_BASE_DELAY ** (attempt + 1)
                        logger.warning(f"Tentativa {attempt + 1} falhou para {item.filename}: {e}")
                        await asyncio.sleep(delay)
                    else:
                        result = DownloadResult(item=item, success=False, error=str(e))
                        self.stats.completed += 1
                        self.stats.failed += 1
                        self.on_result(result)
                        self.on_progress(self.stats)

    async def _do_download(self, session: aiohttp.ClientSession, item: MediaItem, dest: str) -> int:
        total_size = 0
        headers = {}
        if item.album_id:
            headers["Referer"] = f"https://www.erome.com/a/{item.album_id}"

        async with session.get(item.url, headers=headers) as resp:
            if resp.status in (403, 404, 410):
                raise Exception(f"HTTP {resp.status} - acesso negado ou nao encontrado")
            resp.raise_for_status()

            async with aiofiles.open(dest, "wb") as f:
                async for chunk in resp.content.iter_chunked(CHUNK_SIZE):
                    if self.cancel_event.is_set():
                        raise asyncio.CancelledError("Download cancelado")
                    await f.write(chunk)
                    total_size += len(chunk)

        return total_size

    def _get_dest_dir(self, item: MediaItem) -> str:
        base = self.options.download_dir

        if self.options.search_label:
            base = os.path.join(base, self.options.search_label)

        if self.options.flat_folder:
            return base

        username = item.username or "desconhecido"
        album = item.album_title or item.album_id

        if item.media_type == MediaType.PHOTO:
            subdir = "photos"
        else:
            subdir = "videos"

        return os.path.join(base, f"@{username}", album, subdir)
