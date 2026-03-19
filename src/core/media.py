import re
from urllib.parse import urlparse, unquote
from pathlib import Path

from bs4 import BeautifulSoup

from src.core.models import MediaItem, MediaType


def extract_media_from_album(html: str, album_id: str, album_title: str, username: str) -> list[MediaItem]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen_urls = set()

    photo_count = 0
    video_count = 0

    for group in soup.select("div.media-group"):
        # --- Video ---
        video_tag = group.select_one("video")
        source_tag = group.select_one("video source")
        if source_tag:
            src = (source_tag.get("src") or "").strip()
            if src.startswith("http") and src not in seen_urls:
                seen_urls.add(src)
                video_count += 1

                poster = (video_tag.get("poster") or "").strip() if video_tag else ""
                duration_secs = 0
                dur_el = group.select_one("span.duration")
                if dur_el:
                    duration_secs = _parse_duration(dur_el.get_text(strip=True))

                ext = _get_extension(src, "mp4")
                filename = f"{album_id}_{video_count:03d}_video.{ext}"

                items.append(MediaItem(
                    album_id=album_id,
                    album_title=album_title,
                    media_type=MediaType.VIDEO,
                    url=src,
                    filename=filename,
                    username=username,
                    duration_seconds=duration_secs,
                    poster_url=poster,
                ))
            continue

        # --- Photo ---
        img_tag = group.select_one("img.img-back")
        if img_tag:
            src = (img_tag.get("data-src") or img_tag.get("src") or "").strip()
            if src.startswith("http") and src not in seen_urls:
                seen_urls.add(src)
                photo_count += 1
                ext = _get_extension(src, "jpg")
                filename = f"{album_id}_{photo_count:03d}_photo.{ext}"

                items.append(MediaItem(
                    album_id=album_id,
                    album_title=album_title,
                    media_type=MediaType.PHOTO,
                    url=src,
                    filename=filename,
                    username=username,
                ))

    return items


def _parse_duration(text: str) -> int:
    text = text.strip()
    parts = text.split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 1:
            return int(parts[0])
    except ValueError:
        pass
    return 0


def extract_albums_from_profile(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    albums = []
    seen_ids = set()

    for album_div in soup.select("div.album"):
        link = album_div.select_one("a.album-link[href*='/a/']")
        if not link:
            continue

        href = link.get("href", "")
        album_id = href.rstrip("/").split("/a/")[-1]
        if not album_id or album_id in seen_ids:
            continue
        seen_ids.add(album_id)

        title_el = album_div.select_one("a.album-title")
        title = title_el.get_text(strip=True) if title_el else album_id

        album_url = href if href.startswith("http") else f"https://www.erome.com/a/{album_id}"

        albums.append({
            "id": album_id,
            "title": _sanitize_filename(title),
            "url": album_url,
        })

    return albums


def extract_username_from_album(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    user_link = soup.select_one("a#user_name")
    if user_link:
        text = user_link.get_text(strip=True)
        if text:
            return text
        href = user_link.get("href", "")
        username = href.rstrip("/").split("/")[-1]
        if username:
            return username

    user_link = soup.select_one("div.user-info a[href]")
    if user_link:
        href = user_link.get("href", "")
        username = href.rstrip("/").split("/")[-1]
        if username and username not in ("login", "register"):
            return username

    return ""


def extract_album_title(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    title_el = soup.select_one("h1.album-title-page")
    if title_el:
        return _sanitize_filename(title_el.get_text(strip=True))

    title_el = soup.select_one("h1")
    if title_el:
        return _sanitize_filename(title_el.get_text(strip=True))

    meta = soup.find("meta", property="og:title")
    if meta and meta.get("content"):
        return _sanitize_filename(meta["content"])

    return ""


def extract_next_page_url(html: str, current_url: str = "") -> str | None:
    soup = BeautifulSoup(html, "html.parser")

    next_link = soup.select_one("ul.pagination li a[rel='next']")
    if next_link:
        href = next_link.get("href", "")
        if href:
            if href.startswith("http"):
                return href
            if href.startswith("?"):
                base = current_url.split("?")[0] if current_url else "https://www.erome.com"
                return f"{base}{href}"
            return f"https://www.erome.com{href}"

    link_tag = soup.select_one("link[rel='next']")
    if link_tag:
        href = link_tag.get("href", "")
        if href:
            return href if href.startswith("http") else f"https://www.erome.com{href}"

    return None


def parse_erome_url(url: str) -> tuple[str, str]:
    url = url.strip().rstrip("/")

    album_match = re.search(r"erome\.com/a/([A-Za-z0-9]+)", url)
    if album_match:
        return "album", album_match.group(1)

    search_match = re.search(r"erome\.com/search\?q=(.+?)(&|$)", url)
    if search_match:
        query = unquote(search_match.group(1))
        if query.startswith("#"):
            return "hashtag", query[1:]
        return "search", query

    profile_match = re.search(r"erome\.com/([A-Za-z0-9_-]+)$", url)
    if profile_match:
        username = profile_match.group(1)
        if username.lower() not in ("a", "search", "explore", "login", "register", "user"):
            return "profile", username

    return "", ""


def _get_extension(url: str, default: str = "jpg") -> str:
    path = urlparse(url).path
    path = unquote(path)
    ext = Path(path).suffix.lstrip(".")
    if ext.lower() in ("jpg", "jpeg", "png", "gif", "webp", "mp4", "webm", "mkv"):
        return ext.lower()
    return default


def _sanitize_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = name.strip('. ')
    if len(name) > 100:
        name = name[:100]
    return name or "sem_titulo"
