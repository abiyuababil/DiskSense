"""
DiskSense - Scanner Engine
Background file scanning with threading support.
Handles: duplicate detection (hash-based), disk usage analysis,
cleanup suggestions, and file search.
"""

import os
import json
import time
import hashlib
import threading
from collections import defaultdict
from pathlib import Path

from utils import (
    safe_stat, get_file_extension, is_likely_temp_file,
    is_likely_cache_dir, categorize_file,
)


class ScanResult:
    """Container for scan results across all features."""

    def __init__(self):
        # Duplicates: hash -> list of (filepath, size, mtime)
        self.duplicates: dict[str, list[tuple[str, int, float]]] = {}

        # Disk usage: list of (path, size, is_dir)
        self.largest_items: list[tuple[str, int, bool]] = []

        # Folder sizes: path -> total_size
        self.folder_sizes: dict[str, int] = {}

        # Cleanup suggestions: list of (filepath, size, reason)
        self.cleanup_suggestions: list[tuple[str, int, str]] = []

        # Category breakdown: category -> (count, total_size)
        self.categories: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))

        # Search results: list of (filepath, size, mtime)
        self.search_results: list[tuple[str, int, float]] = []

        # Stats
        self.total_files = 0
        self.total_size = 0
        self.files_scanned = 0
        self.errors = 0
        self.current_path = ""

    def purge_file(self, filepath: str):
        """Remove a deleted file/folder from all scan result structures."""
        norm_path = os.path.normpath(filepath)

        # 1. Duplicates
        new_dups = {}
        for h, items in self.duplicates.items():
            filtered = [item for item in items if os.path.normpath(item[0]) != norm_path]
            if len(filtered) > 1:
                new_dups[h] = filtered
        self.duplicates = new_dups

        # 2. Largest items
        self.largest_items = [
            item for item in self.largest_items if os.path.normpath(item[0]) != norm_path
        ]

        # 3. Cleanup suggestions
        self.cleanup_suggestions = [
            item for item in self.cleanup_suggestions if os.path.normpath(item[0]) != norm_path
        ]

        # 4. Search results
        self.search_results = [
            item for item in self.search_results if os.path.normpath(item[0]) != norm_path
        ]

    def to_dict(self) -> dict:
        """Serialize result to JSON-friendly dictionary."""
        return {
            "duplicates": self.duplicates,
            "largest_items": self.largest_items,
            "folder_sizes": self.folder_sizes,
            "cleanup_suggestions": self.cleanup_suggestions,
            "categories": dict(self.categories),
            "search_results": self.search_results,
            "total_files": self.total_files,
            "total_size": self.total_size,
            "files_scanned": self.files_scanned,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ScanResult":
        """Deserialize dictionary back into ScanResult."""
        res = cls()
        res.duplicates = data.get("duplicates", {})
        res.largest_items = [tuple(x) for x in data.get("largest_items", [])]
        res.folder_sizes = data.get("folder_sizes", {})
        res.cleanup_suggestions = [tuple(x) for x in data.get("cleanup_suggestions", [])]
        cats = data.get("categories", {})
        res.categories = defaultdict(lambda: (0, 0), {k: tuple(v) for k, v in cats.items()})
        res.search_results = [tuple(x) for x in data.get("search_results", [])]
        res.total_files = data.get("total_files", 0)
        res.total_size = data.get("total_size", 0)
        res.files_scanned = data.get("files_scanned", 0)
        return res


class HistoryManager:
    """Saves and loads past scan reports from JSON."""

    HISTORY_DIR = os.path.expanduser("~/.disksense")
    HISTORY_FILE = os.path.join(HISTORY_DIR, "scan_history.json")

    @classmethod
    def save(cls, scan_type: str, root_path: str, result: ScanResult):
        try:
            os.makedirs(cls.HISTORY_DIR, exist_ok=True)
            history = cls.load_all()
            entry = {
                "id": str(int(time.time())),
                "timestamp": time.time(),
                "date_str": time.strftime("%Y-%m-%d %H:%M:%S"),
                "scan_type": scan_type,
                "root_path": root_path,
                "total_files": result.total_files,
                "total_size": result.total_size,
                "result_dict": result.to_dict(),
            }
            history.insert(0, entry)
            history = history[:20]  # Keep last 20 scans
            with open(cls.HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2)
        except Exception as e:
            print("Failed to save history:", e)

    @classmethod
    def load_all(cls) -> list[dict]:
        if not os.path.exists(cls.HISTORY_FILE):
            return []
        try:
            with open(cls.HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []


IGNORED_SYSTEM_DIRS = {"$recycle.bin", "$recycled", "system volume information", ".git", ".svn", ".idea", ".vscode"}
IGNORED_SYSTEM_FILES = {"pagefile.sys", "hiberfil.sys", "swapfile.sys", "dumpstack.log.tmp"}

def should_skip_dir(d: str) -> bool:
    name = d.lower()
    return name.startswith(".") or name in IGNORED_SYSTEM_DIRS

def should_skip_file(f: str) -> bool:
    return f.lower() in IGNORED_SYSTEM_FILES


class Scanner:
    """Background file scanner with cancellation support."""

    def __init__(self):
        self._cancel = threading.Event()
        self._lock = threading.Lock()
        self._progress_callback = None
        self._complete_callback = None
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def cancel(self):
        """Signal the scanner to stop."""
        self._cancel.set()

    def scan_duplicates(self, root_path: str, progress_cb=None, complete_cb=None):
        """Start scanning for duplicate files in a background thread."""
        if self.is_running:
            return

        self._cancel.clear()
        self._progress_callback = progress_cb
        self._complete_callback = complete_cb
        self._thread = threading.Thread(
            target=self._do_scan_duplicates,
            args=(root_path,),
            daemon=True,
        )
        self._thread.start()

    def scan_disk_usage(self, root_path: str, progress_cb=None, complete_cb=None):
        """Start scanning disk usage in a background thread."""
        if self.is_running:
            return

        self._cancel.clear()
        self._progress_callback = progress_cb
        self._complete_callback = complete_cb
        self._thread = threading.Thread(
            target=self._do_scan_disk_usage,
            args=(root_path,),
            daemon=True,
        )
        self._thread.start()

    def scan_cleanup(self, root_path: str, progress_cb=None, complete_cb=None):
        """Start scanning for cleanup suggestions in a background thread."""
        if self.is_running:
            return

        self._cancel.clear()
        self._progress_callback = progress_cb
        self._complete_callback = complete_cb
        self._thread = threading.Thread(
            target=self._do_scan_cleanup,
            args=(root_path,),
            daemon=True,
        )
        self._thread.start()

    def search_files(self, root_path: str, query: str, progress_cb=None, complete_cb=None):
        """Start searching files in a background thread."""
        if self.is_running:
            return

        self._cancel.clear()
        self._progress_callback = progress_cb
        self._complete_callback = complete_cb
        self._thread = threading.Thread(
            target=self._do_search_files,
            args=(root_path, query),
            daemon=True,
        )
        self._thread.start()

    def _get_estimated_file_count(self, root_path: str) -> int:
        for rec in HistoryManager.load_all():
            if rec.get("root_path") == root_path:
                return rec.get("total_files", 0)
        return 0

    def _emit_progress(self, result: ScanResult, est_total: int = 0):
        if self._progress_callback:
            pct = (result.files_scanned / est_total) if est_total > 0 else -1
            self._progress_callback(result, pct)

    def _emit_complete(self, result: ScanResult):
        if self._complete_callback:
            self._complete_callback(result)

    def _file_hash(self, filepath: str, chunk_size: int = 8192) -> str | None:
        """Compute MD5 hash of a file. Returns None on error."""
        hasher = hashlib.md5()
        try:
            with open(filepath, "rb") as f:
                while True:
                    if self._cancel.is_set():
                        return None
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    hasher.update(chunk)
            return hasher.hexdigest()
        except (PermissionError, OSError, FileNotFoundError):
            return None

    def _quick_hash(self, filepath: str, size: int) -> str | None:
        """Quick hash using first and last 4KB + file size for pre-grouping."""
        try:
            with open(filepath, "rb") as f:
                head = f.read(4096)
                if size > 8192:
                    f.seek(-4096, 2)
                    tail = f.read(4096)
                else:
                    tail = b""
            return hashlib.md5(head + tail + str(size).encode()).hexdigest()
        except (PermissionError, OSError, FileNotFoundError):
            return None

    def _do_scan_duplicates(self, root_path: str):
        """Phase 1: group by size. Phase 2: quick hash. Phase 3: full hash."""
        result = ScanResult()
        est_total = self._get_estimated_file_count(root_path)

        # Phase 1: Group files by size
        size_groups: dict[int, list[str]] = defaultdict(list)

        for dirpath, dirnames, filenames in os.walk(root_path):
            if self._cancel.is_set():
                return

            # Skip hidden/system dirs
            dirnames[:] = [d for d in dirnames if not should_skip_dir(d)]

            for filename in filenames:
                if self._cancel.is_set() or should_skip_file(filename):
                    continue

                filepath = os.path.join(dirpath, filename)
                stat = safe_stat(filepath)
                if stat is None or stat.st_size == 0:
                    continue

                result.files_scanned += 1
                result.current_path = filepath

                if result.files_scanned % 500 == 0:
                    self._emit_progress(result, est_total)

                size_groups[stat.st_size].append(filepath)

        # Phase 2: Quick hash files that share the same size
        quick_hash_groups: dict[str, list[tuple[str, int]]] = defaultdict(list)
        candidates = {s: paths for s, paths in size_groups.items() if len(paths) > 1}

        result.current_path = "Hashing candidates (quick)..."
        self._emit_progress(result)

        for size, paths in candidates.items():
            if self._cancel.is_set():
                return
            for filepath in paths:
                if self._cancel.is_set():
                    return
                qh = self._quick_hash(filepath, size)
                if qh:
                    quick_hash_groups[qh].append((filepath, size))

        # Phase 3: Full hash where quick hashes match
        full_hash_groups: dict[str, list[tuple[str, int, float]]] = defaultdict(list)
        qh_candidates = {qh: items for qh, items in quick_hash_groups.items() if len(items) > 1}

        result.current_path = "Verifying duplicates (full hash)..."
        self._emit_progress(result)

        for qh, items in qh_candidates.items():
            if self._cancel.is_set():
                return
            for filepath, size in items:
                if self._cancel.is_set():
                    return
                fh = self._file_hash(filepath)
                if fh:
                    stat = safe_stat(filepath)
                    mtime = stat.st_mtime if stat else 0
                    full_hash_groups[fh].append((filepath, size, mtime))

        # Keep only actual duplicates (2+ files with same full hash)
        result.duplicates = {
            h: files for h, files in full_hash_groups.items()
            if len(files) > 1
        }

        result.total_files = result.files_scanned
        self._emit_complete(result)

    def _do_scan_disk_usage(self, root_path: str):
        """Scan and calculate folder sizes, find largest items."""
        result = ScanResult()
        est_total = self._get_estimated_file_count(root_path)
        all_items: list[tuple[str, int, bool]] = []

        # Calculate folder sizes with topdown=True so dirnames[:] pruning works
        for dirpath, dirnames, filenames in os.walk(root_path, topdown=True):
            if self._cancel.is_set():
                return

            dirnames[:] = [d for d in dirnames if not should_skip_dir(d)]

            for filename in filenames:
                if self._cancel.is_set() or should_skip_file(filename):
                    continue

                filepath = os.path.join(dirpath, filename)
                stat = safe_stat(filepath)
                if stat is None:
                    continue

                file_size = stat.st_size
                result.files_scanned += 1
                result.total_size += file_size

                # Track individual files
                all_items.append((filepath, file_size, False))

                # Track categories
                cat = categorize_file(filepath)
                count, total = result.categories[cat]
                result.categories[cat] = (count + 1, total + file_size)

                # Rollup size to ancestor directories up to root_path
                curr = dirpath
                while curr:
                    result.folder_sizes[curr] = result.folder_sizes.get(curr, 0) + file_size
                    if curr == root_path or len(curr) <= len(root_path):
                        break
                    parent = os.path.dirname(curr)
                    if parent == curr:
                        break
                    curr = parent

                if result.files_scanned % 500 == 0:
                    result.current_path = filepath
                    self._emit_progress(result, est_total)

        # Collect folder entries into all_items
        for folder_path, folder_sz in result.folder_sizes.items():
            all_items.append((folder_path, folder_sz, True))

        # Sort by size descending and keep top items
        all_items.sort(key=lambda x: x[1], reverse=True)

        # Keep top 100 files and top 100 folders separately
        files_only = [(p, s, d) for p, s, d in all_items if not d][:200]
        dirs_only = [(p, s, d) for p, s, d in all_items if d][:200]
        result.largest_items = dirs_only + files_only

        result.total_files = result.files_scanned
        self._emit_complete(result)

    def _do_scan_cleanup(self, root_path: str):
        """Scan for files that are safe to clean up."""
        result = ScanResult()
        est_total = self._get_estimated_file_count(root_path)

        for dirpath, dirnames, filenames in os.walk(root_path):
            if self._cancel.is_set():
                return

            orig_dirnames = dirnames[:]
            dirnames[:] = [d for d in dirnames if not should_skip_dir(d)]

            # Check for cache directories
            for d in orig_dirnames:
                if should_skip_dir(d):
                    continue
                full_dir = os.path.join(dirpath, d)
                if is_likely_cache_dir(full_dir):
                    dir_size = self._calc_dir_size(full_dir)
                    if dir_size > 0:
                        result.cleanup_suggestions.append(
                            (full_dir, dir_size, f"Cache/build directory: {d}")
                        )

            for filename in filenames:
                if self._cancel.is_set() or should_skip_file(filename):
                    continue

                filepath = os.path.join(dirpath, filename)
                stat = safe_stat(filepath)
                if stat is None:
                    continue

                result.files_scanned += 1
                result.total_size += stat.st_size

                if result.files_scanned % 500 == 0:
                    result.current_path = filepath
                    self._emit_progress(result, est_total)

                # Check for temp files
                if is_likely_temp_file(filepath):
                    result.cleanup_suggestions.append(
                        (filepath, stat.st_size, "Temporary/cache file")
                    )
                    continue

                # Check for very old large files (> 100MB, not accessed in 1 year)
                import time
                one_year_ago = time.time() - 365 * 86400
                if stat.st_size > 100 * 1024 * 1024 and stat.st_atime < one_year_ago:
                    result.cleanup_suggestions.append(
                        (filepath, stat.st_size, "Large file, not accessed in 1+ year")
                    )

                # Check for old downloads (common download extensions > 50MB, old)
                ext = get_file_extension(filepath)
                six_months_ago = time.time() - 180 * 86400
                if ext in {"exe", "msi", "iso", "dmg", "zip", "rar", "7z"}:
                    if stat.st_size > 50 * 1024 * 1024 and stat.st_mtime < six_months_ago:
                        result.cleanup_suggestions.append(
                            (filepath, stat.st_size, "Old installer/archive (6+ months)")
                        )

        # Sort by size descending
        result.cleanup_suggestions.sort(key=lambda x: x[1], reverse=True)
        result.total_files = result.files_scanned
        self._emit_complete(result)

    def _do_search_files(self, root_path: str, query: str):
        """Search for files matching the query."""
        result = ScanResult()
        query_lower = query.lower()

        for dirpath, dirnames, filenames in os.walk(root_path):
            if self._cancel.is_set():
                return

            dirnames[:] = [d for d in dirnames if not should_skip_dir(d)]

            for filename in filenames:
                if self._cancel.is_set() or should_skip_file(filename):
                    continue

                result.files_scanned += 1

                if result.files_scanned % 500 == 0:
                    result.current_path = os.path.join(dirpath, filename)
                    self._emit_progress(result)

                if query_lower in filename.lower():
                    filepath = os.path.join(dirpath, filename)
                    stat = safe_stat(filepath)
                    if stat:
                        result.search_results.append(
                            (filepath, stat.st_size, stat.st_mtime)
                        )

            # Also match directory names
            for dirname in dirnames:
                if query_lower in dirname.lower():
                    full_dir = os.path.join(dirpath, dirname)
                    result.search_results.append(
                        (full_dir, 0, 0)
                    )

        result.total_files = result.files_scanned
        self._emit_complete(result)

    def _calc_dir_size(self, dirpath: str) -> int:
        """Calculate total size of a directory."""
        total = 0
        try:
            for dp, _, fns in os.walk(dirpath):
                for fn in fns:
                    stat = safe_stat(os.path.join(dp, fn))
                    if stat:
                        total += stat.st_size
        except (PermissionError, OSError):
            pass
        return total
