import os
from pathlib import Path

APP_NAME = "EromeDownloader"
APP_VERSION = "1.1.0"

DATA_DIR = Path.home() / ".eromedl"
SETTINGS_FILE = DATA_DIR / "settings.json"

DEFAULT_DOWNLOAD_DIR = str(Path.home() / "Downloads" / "EromeMedia")

DEFAULT_WORKERS = 10
MAX_WORKERS = 30
MIN_WORKERS = 1

CHUNK_SIZE = 131072  # 128KB
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2

PAGINATION_DELAY = 0.5
ALBUM_SCRAPE_PARALLEL = 4
RATE_LIMIT_DELAY = 30
MAX_PAGE_RETRIES = 3
MAX_EMPTY_PAGES = 3

DOWNLOAD_TIMEOUT = 300  # 5 min per file
CONNECT_TIMEOUT = 15

BASE_URL = "https://www.erome.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.erome.com/",
    "Origin": "https://www.erome.com",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
}

DOWNLOAD_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Encoding": "identity",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
    "Referer": "https://www.erome.com/",
    "Origin": "https://www.erome.com",
    "Sec-Fetch-Dest": "video",
    "Sec-Fetch-Mode": "no-cors",
    "Sec-Fetch-Site": "cross-site",
}


def ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
