"""
DiskSense - Utility helpers
File size formatting, time formatting, and common path operations.
"""

import os
import time
from pathlib import Path


def format_size(size_bytes: int) -> str:
    """Format bytes into human-readable size string."""
    if size_bytes < 0:
        return "0 B"
    if size_bytes == 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    size = float(size_bytes)

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    if unit_index == 0:
        return f"{int(size)} B"
    return f"{size:.1f} {units[unit_index]}"


def format_time_ago(timestamp: float) -> str:
    """Format a timestamp as relative time (e.g., '3 days ago')."""
    diff = time.time() - timestamp
    if diff < 60:
        return "just now"
    elif diff < 3600:
        mins = int(diff / 60)
        return f"{mins}m ago"
    elif diff < 86400:
        hrs = int(diff / 3600)
        return f"{hrs}h ago"
    elif diff < 2592000:
        days = int(diff / 86400)
        return f"{days}d ago"
    elif diff < 31536000:
        months = int(diff / 2592000)
        return f"{months}mo ago"
    else:
        years = int(diff / 31536000)
        return f"{years}y ago"


def format_timestamp(timestamp: float) -> str:
    """Format timestamp to readable date string."""
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(timestamp))


def get_file_extension(filepath: str) -> str:
    """Get lowercase file extension without dot."""
    return Path(filepath).suffix.lower().lstrip(".")


def is_likely_temp_file(filepath: str) -> bool:
    """Check if a file looks like a temporary/cache file that's safe to clean."""
    name = os.path.basename(filepath).lower()
    ext = get_file_extension(filepath)

    temp_extensions = {
        "tmp", "temp", "bak", "old", "orig", "swp", "swo",
        "pyc", "pyo", "__pycache__", "log", "cache",
        "thumbs.db", "desktop.ini", ".ds_store",
    }

    temp_prefixes = ("~", "._", ".~")
    temp_names = {
        "thumbs.db", "desktop.ini", ".ds_store",
        "npm-debug.log", "yarn-error.log",
    }

    if ext in temp_extensions:
        return True
    if name in temp_names:
        return True
    if any(name.startswith(p) for p in temp_prefixes):
        return True
    return False


def is_likely_cache_dir(dirpath: str) -> bool:
    """Check if a directory is a common cache/temp directory."""
    name = os.path.basename(dirpath).lower()
    cache_names = {
        "__pycache__", ".cache", "cache", ".tmp", "tmp", "temp",
        "node_modules", ".tox", ".pytest_cache", ".mypy_cache",
        ".sass-cache", ".parcel-cache", ".next", ".nuxt",
        "dist", "build", ".gradle", ".idea",
    }
    return name in cache_names


def categorize_file(filepath: str) -> str:
    """Categorize a file by its extension."""
    ext = get_file_extension(filepath)

    categories = {
        "Images": {"jpg", "jpeg", "png", "gif", "bmp", "svg", "webp", "ico", "tiff", "raw", "cr2", "nef"},
        "Videos": {"mp4", "avi", "mkv", "mov", "wmv", "flv", "webm", "m4v", "3gp"},
        "Audio": {"mp3", "wav", "flac", "aac", "ogg", "wma", "m4a", "opus"},
        "Documents": {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods", "odp", "txt", "rtf", "csv"},
        "Archives": {"zip", "rar", "7z", "tar", "gz", "bz2", "xz", "iso"},
        "Code": {"py", "js", "ts", "jsx", "tsx", "html", "css", "java", "cpp", "c", "h", "cs", "go", "rs", "rb", "php", "swift", "kt"},
        "Executables": {"exe", "msi", "bat", "cmd", "ps1", "sh", "app", "dmg"},
        "Fonts": {"ttf", "otf", "woff", "woff2", "eot"},
        "Data": {"json", "xml", "yaml", "yml", "toml", "ini", "cfg", "conf", "sql", "db", "sqlite"},
    }

    for category, extensions in categories.items():
        if ext in extensions:
            return category

    return "Other"


def safe_stat(filepath: str):
    """Safely get file stats, returns None on error."""
    try:
        return os.stat(filepath)
    except (PermissionError, OSError, FileNotFoundError):
        return None


def get_available_drives():
    """Get list of available drive letters on Windows."""
    drives = []
    if os.name == "nt":
        import string
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                try:
                    total, used, free = get_drive_usage(drive)
                    drives.append({
                        "path": drive,
                        "letter": letter,
                        "total": total,
                        "used": used,
                        "free": free,
                    })
                except Exception:
                    drives.append({
                        "path": drive,
                        "letter": letter,
                        "total": 0,
                        "used": 0,
                        "free": 0,
                    })
    return drives


def get_drive_usage(path: str):
    """Get drive usage stats. Returns (total, used, free) in bytes."""
    import shutil
    usage = shutil.disk_usage(path)
    return usage.total, usage.used, usage.free
