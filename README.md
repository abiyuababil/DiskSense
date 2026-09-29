# DiskSense

Aplikasi desktop Windows untuk manajemen dan analisis file. Dibuat dengan Python 3.12 + CustomTkinter.

---

## Cara Menjalankan

```bash
# Langsung
python app.py

# Atau double-click
DiskSense.bat
```

### Dependencies

| Package | Versi | Fungsi |
|---|---|---|
| `customtkinter` | 6.0.0 | GUI framework (dark mode, modern widgets) |
| `send2trash` | 2.1.0 | Hapus file ke Recycle Bin (bukan permanent delete) |
| `Pillow` | - | Sudah terinstall, belum dipakai (cadangan untuk thumbnail) |

Install:
```bash
pip install customtkinter send2trash
```

---

## Struktur Project

```
DiskSense/
├── app.py            # Main application, 917 baris
│                     # Entry point, 4 view builders, GUI layout
├── scanner.py        # Scanner engine, 431 baris
│                     # Background scanning dengan threading
├── components.py     # Reusable UI components, 358 baris
│                     # Semua widget custom
├── theme.py          # Design tokens, 64 baris
│                     # Warna, font, spacing
├── utils.py          # Helper functions, 165 baris
│                     # Format size, categorize file, detect temp
├── DiskSense.bat     # Windows launcher
└── README.md         # File ini
```

---

## Arsitektur

### Pola Utama

```
app.py (DiskSenseApp)
  ├── scanner.py (Scanner)        → Background thread, emit progress/complete
  ├── components.py (Widgets)     → UI building blocks
  ├── theme.py (Colors/Fonts)     → Design system
  └── utils.py (Helpers)          → Pure functions, no state
```

**Threading model:** Semua scan operasi berjalan di `threading.Thread(daemon=True)`. Scanner mengirim update ke GUI via `self.after(100, callback)` untuk thread-safety (Tkinter hanya bisa diupdate dari main thread). Setiap scan bisa di-cancel via `threading.Event`.

**State management:** `DiskSenseApp` menyimpan:
- `_scanner` (Scanner) - singleton scanner instance
- `_current_view` (int) - view aktif (0-3)
- `_scan_target` (str) - path folder yang dipilih
- `_results` (dict[int, ScanResult]) - hasil scan per view (0: duplicates, 1: disk usage, 2: cleanup, 3: search). Hasil tersimpan saat pindah tab.

---

## Fitur Detail

### 1. Duplicate File Finder (View Index 0)

**File:** `app.py` method `_build_duplicates_view`, `_start_duplicate_scan`, `_render_duplicates`
**Scanner:** `scanner.py` method `_do_scan_duplicates`

**Algoritma 3-fase:**

| Fase | Method | Apa yang dilakukan |
|---|---|---|
| 1. Group by size | `_do_scan_duplicates` L170-198 | Walk semua file, group berdasarkan `st_size`. File dengan ukuran unik langsung diskip. |
| 2. Quick hash | `_quick_hash` L152-164 | Baca 4KB pertama + 4KB terakhir + file size, hash MD5. Cepat karena hanya baca 8KB per file. |
| 3. Full hash | `_file_hash` L136-150 | MD5 full file content, baca per 8KB chunk. Hanya untuk file yang quick hash-nya cocok. |

**Kenapa 3 fase:** Membaca full file content sangat lambat untuk file besar. Fase 1 mengeliminasi ~90% file (ukuran unik). Fase 2 mengeliminasi lagi file yang kebetulan ukurannya sama tapi isinya beda. Fase 3 hanya verifikasi final.

**Data structure hasil:**
```python
ScanResult.duplicates: dict[str, list[tuple[str, int, float]]]
#                      hash -> [(filepath, size_bytes, mtime), ...]
```

**UI rendering:**
- Summary card: total groups, total duplicates, recoverable space
- Groups diurutkan by wasted space (terbesar dulu)
- File pertama di setiap group ditandai "keep (oldest)" dengan background teal
- File lainnya punya tombol delete (✕)
- Max 50 groups ditampilkan

**Skip rules:**
- Hidden directories (dimulai `.`)
- System dirs: `$RECYCLE.BIN`, `System Volume Information`
- File 0 bytes diskip

---

### 2. Disk Usage Analyzer (View Index 1)

**File:** `app.py` method `_build_disk_usage_view`, `_render_disk_usage`, `_switch_usage_tab`
**Scanner:** `scanner.py` method `_do_scan_disk_usage`

**3 sub-tab:**

| Tab | Index | Content |
|---|---|---|
| Largest Folders | 0 | Top 50 folder by total recursive size, visualized as horizontal bars |
| Largest Files | 1 | Top 80 file by size, clickable to open in Explorer |
| By Category | 2 | File count + total size per category (Images, Videos, Audio, dll) |

**Folder size calculation:** `os.walk(topdown=False)` bottom-up. Setiap folder = sum(file sizes) + sum(subfolder sizes yang sudah dihitung). Disimpan di `result.folder_sizes[dirpath]`.

**Category system** (defined in `utils.py` `categorize_file`):

| Category | Extensions |
|---|---|
| Images | jpg, jpeg, png, gif, bmp, svg, webp, ico, tiff, raw, cr2, nef |
| Videos | mp4, avi, mkv, mov, wmv, flv, webm, m4v, 3gp |
| Audio | mp3, wav, flac, aac, ogg, wma, m4a, opus |
| Documents | pdf, doc, docx, xls, xlsx, ppt, pptx, odt, ods, odp, txt, rtf, csv |
| Archives | zip, rar, 7z, tar, gz, bz2, xz, iso |
| Code | py, js, ts, jsx, tsx, html, css, java, cpp, c, h, cs, go, rs, rb, php, swift, kt |
| Executables | exe, msi, bat, cmd, ps1, sh, app, dmg |
| Fonts | ttf, otf, woff, woff2, eot |
| Data | json, xml, yaml, yml, toml, ini, cfg, conf, sql, db, sqlite |
| Other | Semua yang tidak masuk kategori di atas |

**Category warna** (hard-coded di `app.py` L557-568):
- Images: `#e0a84e` (amber)
- Videos: `#e05c5c` (red)
- Audio: `#5b8def` (blue)
- Documents: `#2eb8a6` (teal)
- Archives: `#9b59b6` (purple)
- Code: `#5cb85c` (green)
- Executables: `#e07c5c` (coral)
- Data: `#8e9cc0` (slate)
- Fonts: `#c09b8e` (brown)

**Size bar color logic** (`_size_color`, L580-585):
- `> 30%` of total: red (large proportion)
- `> 10%` of total: amber (medium)
- Default: teal (normal)

---

### 3. Cleanup Suggestions (View Index 2)

**File:** `app.py` method `_build_cleanup_view`, `_render_cleanup`
**Scanner:** `scanner.py` method `_do_scan_cleanup`

**Detection rules:**

| Rule | Kondisi | Reason Text |
|---|---|---|
| Temp files | Extension: tmp, temp, bak, old, orig, swp, swo, pyc, pyo, log, cache. Names: thumbs.db, desktop.ini, .ds_store, npm-debug.log, yarn-error.log. Prefix: `~`, `._`, `.~` | "Temporary/cache file" |
| Cache dirs | Directory name: `__pycache__`, `.cache`, `cache`, `.tmp`, `tmp`, `temp`, `node_modules`, `.tox`, `.pytest_cache`, `.mypy_cache`, `.sass-cache`, `.parcel-cache`, `.next`, `.nuxt`, `dist`, `build`, `.gradle`, `.idea` | "Cache/build directory: {name}" |
| Old large files | Size > 100MB AND last access time > 1 year ago | "Large file, not accessed in 1+ year" |
| Old installers | Extension: exe, msi, iso, dmg, zip, rar, 7z AND size > 50MB AND modified > 6 months ago | "Old installer/archive (6+ months)" |

**UI rendering:**
- Summary card: total items, total recoverable space (amber)
- Grouped by reason, sorted by total size per group
- Max 30 items per group
- Setiap item punya tombol delete (✕)
- Delete = Recycle Bin (via `send2trash`)

---

### 4. File Search (View Index 3)

**File:** `app.py` method `_build_search_view`, `_start_search`, `_render_search`
**Scanner:** `scanner.py` method `_do_search_files`

**Search behavior:**
- Case-insensitive substring match: `query.lower() in filename.lower()`
- Juga match directory names
- Trigger: Enter key atau klik Search button
- Hasil diurutkan by size (terbesar dulu)
- Max 200 results ditampilkan
- Klik filename: buka di Windows Explorer

---

## UI Components (`components.py`)

| Component | Class | Fungsi |
|---|---|---|
| Sidebar nav button | `SidebarButton` | Tombol navigasi sidebar, ada state active/inactive |
| Status bar | `StatusBar` | Bar bawah: status text + progress bar (determinate/indeterminate) + count label |
| File row | `FileRow` | Satu baris file: nama (klik untuk buka) + size + detail text + tombol delete. Hover effect. |
| Section header | `SectionHeader` | Judul section + subtitle + optional action button (e.g., "Scan") |
| Empty state | `EmptyState` | Placeholder ketika belum ada data: icon + title + description, centered |
| Size bar | `SizeBar` | Horizontal bar proporsional untuk visualisasi disk usage |
| Confirm dialog | `ConfirmDialog` | Modal konfirmasi delete: title + message + Cancel/Delete buttons, closable with Escape |

---

## Design System (`theme.py`)

### Palette

| Token | Hex | Penggunaan |
|---|---|---|
| `BG_PRIMARY` | `#1a1d23` | Main background |
| `BG_SECONDARY` | `#22262e` | Sidebar, panels |
| `BG_TERTIARY` | `#2a2f38` | Cards, inputs |
| `BG_HOVER` | `#323842` | Hover state |
| `ACCENT` | `#2eb8a6` | Primary teal accent |
| `ACCENT_HOVER` | `#35d4bf` | Teal hover |
| `ACCENT_MUTED` | `#1a6b60` | Selected/active background |
| `TEXT_PRIMARY` | `#e8eaed` | Main text |
| `TEXT_SECONDARY` | `#9ca3af` | Labels, metadata |
| `TEXT_MUTED` | `#6b7280` | Placeholders, disabled |
| `RED` | `#e05c5c` | Delete, danger |
| `AMBER` | `#e0a84e` | Caution, warnings |
| `GREEN` | `#5cb85c` | Safe, small |
| `BLUE` | `#5b8def` | Info, links |

### Typography

- Body: Segoe UI 13px
- Mono (sizes, paths): Consolas
- Heading: 18px bold
- Subheading: 14px
- Small: 11px
- Tiny: 10px

### Spacing Scale

- XS: 4px, SM: 8px, MD: 12px, LG: 16px, XL: 24px
- Border radius: SM 4px, MD 6px, LG 8px

---

## Application Layout (`app.py`)

```
┌─────────────────────────────────────────────────┐
│ ┌──────────┐ ┌────────────────────────────────┐ │
│ │          │ │                                │ │
│ │ DiskSense│ │        Content Area            │ │
│ │          │ │                                │ │
│ │ 🔍 Dupl  │ │  (switches based on nav)       │ │
│ │ 📊 Disk  │ │                                │ │
│ │ 🧹 Clean │ │  SectionHeader                 │ │
│ │ 🔎 Search│ │  ┌──────────────────────────┐  │ │
│ │          │ │  │ ScrollableList           │  │ │
│ │  (spacer)│ │  │  FileRow / SizeBar /     │  │ │
│ │          │ │  │  EmptyState              │  │ │
│ │ Target:  │ │  │                          │  │ │
│ │ C:\...   │ │  │                          │  │ │
│ │ [Choose] │ │  └──────────────────────────┘  │ │
│ │ C: 50GB  │ │                                │ │
│ │ D: 20GB  │ │                                │ │
│ └──────────┘ └────────────────────────────────┘ │
│ StatusBar: Ready            ████░░░░ 1,234 files│
└─────────────────────────────────────────────────┘
```

- **Sidebar** (220px fixed): App title, 4 nav buttons, spacer, folder picker + drive quick-picks
- **Content area** (expand): Switches content based on active nav
- **Status bar** (32px fixed, bottom): Status text, file count, progress bar
- **Window**: 1100x700 default, 900x550 minimum, resizable

---

## Alur Data (Flow)

```
User klik "Scan"
  → _start_duplicate_scan() (main thread)
  → Check _scan_target, if empty → _pick_folder()
  → Check _scanner.is_running, if true → cancel current scan
  → Clear list, show "Scanning..." label
  → Set status bar indeterminate
  → scanner.scan_duplicates(path, progress_cb, complete_cb)
      → Thread baru: _do_scan_duplicates()
          → os.walk() → group by size → quick hash → full hash
          → Setiap 500 file: progress_cb → self.after(100, _on_dup_progress)
          → Selesai: complete_cb → self.after(100, _on_dup_complete)
  → _on_dup_complete()
      → Save result ke _last_result
      → Stop indeterminate progress
      → Update status text
      → Clear list, call _render_duplicates()
          → Build summary card
          → Build group frames with FileRow per file
```

---

## Aksi User

| Aksi | Method | Behavior |
|---|---|---|
| Klik nama file | `_open_in_explorer(path)` | Folder: `os.startfile()`. File: `explorer /select, path` (highlight di Explorer) |
| Klik ✕ delete | `_confirm_delete(path)` | Buka ConfirmDialog |
| Confirm delete | `_do_delete(path)` | `send2trash(path)` → Recycle Bin |
| Choose Folder | `_pick_folder()` | `filedialog.askdirectory()` |
| Klik drive letter | `_set_folder(path)` | Set scan target langsung |
| Switch tab | `_show_view(index)` | Destroy content, rebuild view |
| Scan saat scanner jalan | Cancel dulu | `_scanner.cancel()` lalu return |

---

## Limitasi Saat Ini

| Area | Limitasi | Solusi Potensial |
|---|---|---|
| Concurrent scan | Hanya 1 scan berjalan sekaligus | Queue system atau multiple Scanner instances |
| Large directories | Scan drive C:\ penuh bisa lambat | Progress estimation, partial results, skip known heavy dirs |
| Hash collision | MD5 collision secara teori bisa terjadi | Upgrade ke SHA-256 (lebih lambat tapi lebih aman) |
| UI rendering | 200+ FileRow widgets bisa lambat | Virtual scrolling / lazy loading |
| Cross-platform | `os.startfile()` dan `explorer` hanya Windows | Platform detection + xdg-open/open untuk Linux/Mac |
| Disk usage tab switch | Mencari tab_frame lewat widget traversal | Simpan reference langsung ke `self._tab_buttons` |
| Export | Tidak bisa export hasil scan | CSV/JSON export |

---

## Status Fitur Terbaru (Selesai Dikerjakan)

1. ✅ **Batch Delete & Purging**: Hapus multiple file sekaligus dengan Checkbox (`Select All` / `Deselect All` / `Delete Selected`). File yang dihapus langsung di-purge dari memori dan hilang dari UI secara real-time.
2. ✅ **Export Hasil Scan**: Tombol export ke format **CSV** & **JSON** di semua menu utama.
3. ✅ **Treemap Visualization**: Visualisasi proporsi ukuran folder & file secara 2D rectangular treemap interaktif berbasis Tkinter `Canvas`.
4. ✅ **Filter Extension Duplicate**: Filter hasil scan duplikat berdasarkan ekstensi (`All`, `Media`, `Docs`, `Archives`, `Code`).
5. ✅ **Scan History**: Penyimpanan otomatis laporan hasil scan ke `~/.disksense/scan_history.json` dan menu **History** untuk memuat ulang laporan scan sebelumnya tanpa scan ulang.
6. ✅ **File Preview Modal (👁)**: Modal preview interaktif yang menampilkan thumbnail gambar (via PIL), 30 baris pertama teks/kode (UTF-8 safe), dan metadata detail file.
7. ✅ **Sort Options Dropdown**: Pengurutan hasil scan di semua menu berdasarkan `Size (Desc)`, `Size (Asc)`, `Name (A-Z)`, `Name (Z-A)`, dan `Date (Newest)`.
8. ✅ **Progress Percentage Estimation**: Estimasi persentase kemajuan scan berbasis riwayat scan sebelumnya (`0% - 99%` pada status bar).

---

## Ide Pengembangan Selanjutnya

9. **Scheduled scan** (auto scan berkala)
10. **Exclude patterns** (ignore specific folders/extensions)
