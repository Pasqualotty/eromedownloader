from dataclasses import dataclass, field
from enum import Enum


class MediaType(Enum):
    PHOTO = "photo"
    VIDEO = "video"


class DownloadMode(Enum):
    ALBUM = "album"
    PROFILE = "profile"
    SEARCH = "search"
    HASHTAG = "hashtag"


@dataclass
class MediaItem:
    album_id: str
    album_title: str
    media_type: MediaType
    url: str
    filename: str
    username: str = ""
    duration_seconds: int = 0
    poster_url: str = ""


@dataclass
class DownloadResult:
    item: MediaItem
    success: bool
    file_size: int = 0
    error: str = ""
    skipped: bool = False


@dataclass
class DownloadStats:
    total: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    total_bytes: int = 0


@dataclass
class DownloadOptions:
    url: str = ""
    mode: DownloadMode = DownloadMode.ALBUM
    download_dir: str = ""
    download_photos: bool = True
    download_videos: bool = True
    workers: int = 5
    limit: int = 0
    video_min_seconds: int = 0
    video_max_seconds: int = 0
    face_filter: bool = False
