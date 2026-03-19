import asyncio
import logging
from urllib.parse import quote
from typing import Callable

import aiohttp

from src.utils.config import (
    BASE_URL, HEADERS, DOWNLOAD_HEADERS, PAGINATION_DELAY, RATE_LIMIT_DELAY,
    MAX_PAGE_RETRIES, MAX_EMPTY_PAGES, ALBUM_SCRAPE_PARALLEL, CONNECT_TIMEOUT,
)
from src.core.models import MediaItem, MediaType, DownloadOptions
from src.core.media import (
    extract_media_from_album,
    extract_albums_from_profile,
    extract_username_from_album,
    extract_album_title,
    extract_next_page_url,
    parse_erome_url,
    _sanitize_filename,
)
from src.core.face_detect import detect_face_in_image_bytes

logger = logging.getLogger(__name__)


def _fmt_duration(secs: int) -> str:
    m, s = divmod(secs, 60)
    return f"{m}:{s:02d}"


class EromeScraper:
    def __init__(
        self,
        options: DownloadOptions,
        on_status: Callable[[str], None] | None = None,
        on_scrape_progress: Callable[[int, int], None] | None = None,
        cancel_event: asyncio.Event | None = None,
    ):
        self.options = options
        self.on_status = on_status or (lambda msg: None)
        self.on_scrape_progress = on_scrape_progress or (lambda found, albums: None)
        self.cancel_event = cancel_event or asyncio.Event()
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=60, connect=CONNECT_TIMEOUT)
            connector = aiohttp.TCPConnector(
                limit=20,
                ttl_dns_cache=600,
                enable_cleanup_closed=True,
                keepalive_timeout=30,
            )
            self._session = aiohttp.ClientSession(
                headers=HEADERS,
                connector=connector,
                timeout=timeout,
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def fetch_page(self, url: str) -> str:
        session = await self._get_session()
        for attempt in range(MAX_PAGE_RETRIES):
            if self.cancel_event.is_set():
                return ""
            try:
                async with session.get(url) as resp:
                    if resp.status == 429:
                        self.on_status(f"Rate limit atingido, aguardando {RATE_LIMIT_DELAY}s...")
                        await asyncio.sleep(RATE_LIMIT_DELAY)
                        continue
                    if resp.status == 404:
                        self.on_status(f"Pagina nao encontrada: {url}")
                        return ""
                    resp.raise_for_status()
                    return await resp.text()
            except asyncio.TimeoutError:
                if attempt < MAX_PAGE_RETRIES - 1:
                    self.on_status(f"Timeout ao acessar pagina, tentando novamente...")
                    await asyncio.sleep(2)
                else:
                    self.on_status(f"Timeout: {url}")
                    return ""
            except aiohttp.ClientError as e:
                if attempt < MAX_PAGE_RETRIES - 1:
                    delay = 2 ** (attempt + 1)
                    self.on_status(f"Erro ao acessar pagina, tentando novamente em {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    self.on_status(f"Falha ao acessar: {url} - {e}")
                    return ""
        return ""

    async def _fetch_image_bytes(self, url: str) -> bytes | None:
        if not url:
            return None
        session = await self._get_session()
        try:
            async with session.get(url, headers=DOWNLOAD_HEADERS) as resp:
                if resp.status == 200:
                    return await resp.read()
        except Exception as e:
            logger.warning(f"Erro ao baixar thumbnail: {e}")
        return None

    async def scrape_album(self, album_id: str) -> list[MediaItem]:
        url = f"{BASE_URL}/a/{album_id}"
        self.on_status(f"Acessando album: {album_id}")

        html = await self.fetch_page(url)
        if not html:
            return []

        username = extract_username_from_album(html)
        title = extract_album_title(html) or album_id

        self.on_status(f"Album: {title}" + (f" | {username}" if username else ""))

        items = extract_media_from_album(html, album_id, title, username)
        items = self._filter_items(items)
        items = self._filter_duration(items)
        items = await self._filter_faces(items)

        self.on_status(f"  -> {len(items)} itens")
        return items

    async def _scrape_album_batch(self, albums: list[dict], folder_prefix: str) -> list[MediaItem]:
        sem = asyncio.Semaphore(ALBUM_SCRAPE_PARALLEL)
        results: list[list[MediaItem]] = []

        async def _do(album: dict):
            async with sem:
                if self.cancel_event.is_set():
                    return []
                items = await self.scrape_album(album["id"])
                if folder_prefix:
                    for item in items:
                        if not item.username:
                            item.username = folder_prefix
                return items

        tasks = [_do(album) for album in albums]
        batch_results = await asyncio.gather(*tasks)
        for r in batch_results:
            results.append(r)

        all_items = []
        for r in results:
            all_items.extend(r)
        return all_items

    async def _scrape_paginated(self, first_url: str, label: str, folder_prefix: str = "") -> list[MediaItem]:
        self.on_status(f"Buscando: {label}")

        all_items: list[MediaItem] = []
        page_url: str | None = first_url
        empty_pages = 0
        page_num = 0
        total_albums = 0

        while page_url and not self.cancel_event.is_set():
            page_num += 1
            html = await self.fetch_page(page_url)
            if not html:
                empty_pages += 1
                if empty_pages >= MAX_EMPTY_PAGES:
                    break
                continue

            albums = extract_albums_from_profile(html)

            if not albums:
                empty_pages += 1
                if empty_pages >= MAX_EMPTY_PAGES:
                    self.on_status("Nenhum album encontrado nas ultimas paginas, finalizando.")
                    break
            else:
                empty_pages = 0

            total_albums += len(albums)
            self.on_status(f"Pagina {page_num}: {len(albums)} albums encontrados")
            self.on_scrape_progress(len(all_items), total_albums)

            page_items = await self._scrape_album_batch(albums, folder_prefix)
            all_items.extend(page_items)
            self.on_scrape_progress(len(all_items), total_albums)

            if self.options.limit > 0 and len(all_items) >= self.options.limit:
                self.on_status(f"Limite de {self.options.limit} itens atingido.")
                return all_items[:self.options.limit]

            next_url = extract_next_page_url(html, current_url=page_url)
            if next_url and next_url != page_url:
                page_url = next_url
                self.on_status(f"Proxima pagina...")
                await asyncio.sleep(PAGINATION_DELAY)
            else:
                page_url = None

        self.on_status(f"Busca finalizada: {len(all_items)} midias em {total_albums} albums")
        return all_items

    async def scrape_profile(self, username: str) -> list[MediaItem]:
        first_url = f"{BASE_URL}/{username}"
        items = await self._scrape_paginated(first_url, f"Perfil: {username}", folder_prefix=username)
        for item in items:
            item.username = username
        return items

    async def scrape_search(self, query: str) -> list[MediaItem]:
        encoded = quote(query)
        first_url = f"{BASE_URL}/search?q={encoded}"
        folder = f"busca_{_sanitize_filename(query)}"
        return await self._scrape_paginated(first_url, f"Busca: \"{query}\"", folder_prefix=folder)

    async def scrape_hashtag(self, tag: str) -> list[MediaItem]:
        encoded = quote(f"#{tag}")
        first_url = f"{BASE_URL}/search?q={encoded}"
        folder = f"tag_{_sanitize_filename(tag)}"
        return await self._scrape_paginated(first_url, f"Hashtag: #{tag}", folder_prefix=folder)

    async def scrape(self) -> list[MediaItem]:
        url_type, identifier = parse_erome_url(self.options.url)

        if url_type == "album":
            self.on_scrape_progress(-1, 0)
            items = await self.scrape_album(identifier)
        elif url_type == "profile":
            items = await self.scrape_profile(identifier)
        elif url_type == "search":
            items = await self.scrape_search(identifier)
        elif url_type == "hashtag":
            items = await self.scrape_hashtag(identifier)
        else:
            self.on_status("URL/termo invalido. Use uma URL do Erome, termo de busca, ou #hashtag")
            return []

        if self.options.limit > 0:
            items = items[:self.options.limit]

        return items

    def _filter_items(self, items: list[MediaItem]) -> list[MediaItem]:
        filtered = []
        for item in items:
            if item.media_type == MediaType.PHOTO and not self.options.download_photos:
                continue
            if item.media_type == MediaType.VIDEO and not self.options.download_videos:
                continue
            filtered.append(item)
        return filtered

    def _filter_duration(self, items: list[MediaItem]) -> list[MediaItem]:
        min_s = self.options.video_min_seconds
        max_s = self.options.video_max_seconds
        if min_s <= 0 and max_s <= 0:
            return items

        filtered = []
        for item in items:
            if item.media_type != MediaType.VIDEO:
                filtered.append(item)
                continue

            dur = item.duration_seconds
            if dur <= 0:
                self.on_status(
                    f"  Filtrado (duracao desconhecida): {item.filename}"
                )
                continue

            if min_s > 0 and dur < min_s:
                self.on_status(
                    f"  Filtrado (curto): {item.filename} "
                    f"({_fmt_duration(dur)} < {_fmt_duration(min_s)})"
                )
                continue
            if max_s > 0 and dur > max_s:
                self.on_status(
                    f"  Filtrado (longo): {item.filename} "
                    f"({_fmt_duration(dur)} > {_fmt_duration(max_s)})"
                )
                continue

            self.on_status(
                f"  OK: {item.filename} ({_fmt_duration(dur)})"
            )
            filtered.append(item)
        return filtered

    async def _filter_faces(self, items: list[MediaItem]) -> list[MediaItem]:
        if not self.options.face_filter:
            return items

        filtered = []
        for item in items:
            if item.media_type != MediaType.VIDEO:
                filtered.append(item)
                continue

            if not item.poster_url:
                filtered.append(item)
                continue

            self.on_status(f"  Verificando rosto: {item.filename}...")
            img_data = await self._fetch_image_bytes(item.poster_url)
            if img_data is None:
                filtered.append(item)
                continue

            has_face = detect_face_in_image_bytes(img_data)
            if has_face:
                self.on_status(f"  Rosto detectado: {item.filename}")
                filtered.append(item)
            else:
                self.on_status(f"  Sem rosto, ignorado: {item.filename}")

        return filtered
