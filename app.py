"""
DiskSense - Main Application
Desktop file management tool with 5 core features:
  1. Duplicate File Finder (with Extension Filter)
  2. Disk Usage Analyzer (with Treemap Visualization)
  3. Cleanup Suggestions
  4. File Search
  5. Scan History Report Viewer
"""

import os
import csv
import json
import subprocess
import threading
import customtkinter as ctk
from tkinter import filedialog

from theme import Colors, Fonts, Spacing
from utils import format_size, format_time_ago, format_timestamp, get_available_drives, get_file_extension
from scanner import Scanner, ScanResult, HistoryManager
from components import (
    SidebarButton, StatusBar, FileRow, SectionHeader,
    EmptyState, SizeBar, ConfirmDialog, TreemapCanvas,
    FilePreviewDialog,
)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


class ScrollableList(ctk.CTkScrollableFrame):
    """Scrollable frame for file lists."""

    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color="transparent",
            scrollbar_button_color=Colors.SCROLLBAR,
            scrollbar_button_hover_color=Colors.SCROLLBAR_HOVER,
            **kwargs,
        )

    def clear(self):
        for widget in self.winfo_children():
            widget.destroy()


class DiskSenseApp(ctk.CTk):
    """Main application window."""

    NAV_ITEMS = [
        ("Duplicates", "🔍"),
        ("Disk Usage", "📊"),
        ("Cleanup", "🧹"),
        ("Search", "🔎"),
        ("History", "📜"),
    ]

    def __init__(self):
        super().__init__()

        self.title("DiskSense")
        self.geometry("1150x740")
        self.minsize(950, 600)
        self.configure(fg_color=Colors.BG_PRIMARY)

        # State
        self._scanner = Scanner()
        self._current_view = 0
        self._scan_target = ""
        self._results: dict[int, ScanResult | None] = {0: None, 1: None, 2: None, 3: None}
        self._selected_files: set[str] = set()
        self._dup_ext_filter = "All"
        self._search_query = ""
        self._usage_tab_index = 0
        self._sort_mode = "Size (Desc)"

        self._build_layout()
        self._show_view(0)

    def _build_layout(self):
        """Build the main layout: sidebar + content + status bar."""
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True)

        # Sidebar
        sidebar = ctk.CTkFrame(main, width=220, corner_radius=0, fg_color=Colors.BG_SECONDARY)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        # App title
        title_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        title_frame.pack(fill="x", padx=Spacing.PAD_LG, pady=(Spacing.PAD_XL, Spacing.PAD_SM))

        ctk.CTkLabel(
            title_frame,
            text="DiskSense",
            font=ctk.CTkFont(family=Fonts.FAMILY, size=20, weight="bold"),
            text_color=Colors.ACCENT,
            anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_frame,
            text="File Manager & Analyzer",
            font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.TINY_SIZE),
            text_color=Colors.TEXT_MUTED,
            anchor="w",
        ).pack(anchor="w", pady=(0, Spacing.PAD_SM))

        # Divider
        ctk.CTkFrame(sidebar, height=1, fg_color=Colors.BORDER).pack(fill="x", padx=Spacing.PAD_LG)

        # Nav buttons
        nav_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        nav_frame.pack(fill="x", padx=Spacing.PAD_SM, pady=Spacing.PAD_MD)

        self._nav_buttons: list[SidebarButton] = []
        for i, (label, icon) in enumerate(self.NAV_ITEMS):
            btn = SidebarButton(
                nav_frame,
                text=label,
                icon_text=icon,
                active=(i == 0),
                command=lambda idx=i: self._show_view(idx),
            )
            btn.pack(fill="x", pady=2)
            self._nav_buttons.append(btn)

        # Spacer
        ctk.CTkFrame(sidebar, fg_color="transparent").pack(fill="both", expand=True)

        # Folder picker at bottom of sidebar
        picker_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        picker_frame.pack(fill="x", padx=Spacing.PAD_SM, pady=Spacing.PAD_MD)

        ctk.CTkLabel(
            picker_frame,
            text="Target Folder",
            font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.TINY_SIZE),
            text_color=Colors.TEXT_MUTED,
            anchor="w",
        ).pack(anchor="w", padx=Spacing.PAD_SM)

        self._path_label = ctk.CTkLabel(
            picker_frame,
            text="No folder selected",
            font=ctk.CTkFont(family=Fonts.MONO, size=Fonts.TINY_SIZE),
            text_color=Colors.TEXT_SECONDARY,
            anchor="w",
            wraplength=190,
        )
        self._path_label.pack(anchor="w", padx=Spacing.PAD_SM, pady=(2, Spacing.PAD_SM))

        ctk.CTkButton(
            picker_frame,
            text="Choose Folder",
            height=34,
            corner_radius=Spacing.RADIUS_MD,
            fg_color=Colors.BG_TERTIARY,
            hover_color=Colors.BG_HOVER,
            text_color=Colors.TEXT_PRIMARY,
            border_width=1,
            border_color=Colors.BORDER,
            font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.BODY_SIZE),
            command=self._pick_folder,
        ).pack(fill="x", padx=Spacing.PAD_SM)

        # Drive quick picks
        drives = get_available_drives()
        if drives:
            drive_frame = ctk.CTkFrame(picker_frame, fg_color="transparent")
            drive_frame.pack(fill="x", padx=Spacing.PAD_SM, pady=(Spacing.PAD_SM, 0))

            for drive in drives[:4]:
                btn_text = f"{drive['letter']}:  {format_size(drive['free'])} free"
                ctk.CTkButton(
                    drive_frame,
                    text=btn_text,
                    height=26,
                    corner_radius=Spacing.RADIUS_SM,
                    fg_color="transparent",
                    hover_color=Colors.BG_HOVER,
                    text_color=Colors.TEXT_SECONDARY,
                    anchor="w",
                    font=ctk.CTkFont(family=Fonts.MONO, size=Fonts.TINY_SIZE),
                    command=lambda p=drive["path"]: self._set_folder(p),
                ).pack(fill="x", pady=1)

        # Content area
        self._content = ctk.CTkFrame(main, fg_color=Colors.BG_PRIMARY, corner_radius=0)
        self._content.pack(side="left", fill="both", expand=True)

        # Status bar
        self._status_bar = StatusBar(self)
        self._status_bar.pack(fill="x", side="bottom")

    def _pick_folder(self):
        folder = filedialog.askdirectory(title="Select folder to scan")
        if folder:
            self._set_folder(folder)

    def _set_folder(self, path: str):
        self._scan_target = path
        display = path if len(path) < 35 else "..." + path[-32:]
        self._path_label.configure(text=display)

    def _show_view(self, index: int):
        """Switch to a different view."""
        self._current_view = index
        self._selected_files.clear()
        for i, btn in enumerate(self._nav_buttons):
            btn.set_active(i == index)

        # Clear content
        for w in self._content.winfo_children():
            w.destroy()

        if index == 0:
            self._build_duplicates_view()
        elif index == 1:
            self._build_disk_usage_view()
        elif index == 2:
            self._build_cleanup_view()
        elif index == 3:
            self._build_search_view()
        elif index == 4:
            self._build_history_view()

    # ─── Batch & Selection Helpers ───

    def _on_file_check(self, filepath: str, is_checked: bool):
        if is_checked:
            self._selected_files.add(filepath)
        else:
            self._selected_files.discard(filepath)
        self._update_batch_bar_status()

    def _update_batch_bar_status(self):
        if hasattr(self, "_batch_del_btn") and self._batch_del_btn:
            count = len(self._selected_files)
            if count > 0:
                total_sz = 0
                for p in self._selected_files:
                    try:
                        if os.path.isfile(p):
                            total_sz += os.path.getsize(p)
                    except Exception:
                        pass
                self._batch_del_btn.configure(
                    text=f"Delete Selected ({count} items  ·  {format_size(total_sz)})",
                    state="normal",
                    fg_color=Colors.RED_BG,
                )
            else:
                self._batch_del_btn.configure(
                    text="Delete Selected (0)",
                    state="disabled",
                    fg_color=Colors.BG_TERTIARY,
                )

    def _build_batch_bar(self, parent, available_files: list[str], export_title="Scan Results"):
        """Render a top toolbar with batch selection, batch delete, and export buttons."""
        bar = ctk.CTkFrame(parent, fg_color=Colors.BG_SECONDARY, height=42, corner_radius=Spacing.RADIUS_MD)
        bar.pack(fill="x", pady=(0, Spacing.PAD_MD), padx=2)

        left = ctk.CTkFrame(bar, fg_color="transparent")
        left.pack(side="left", padx=Spacing.PAD_SM, pady=6)

        ctk.CTkButton(
            left,
            text="Select All",
            width=85,
            height=28,
            corner_radius=Spacing.RADIUS_SM,
            fg_color=Colors.BG_TERTIARY,
            hover_color=Colors.BG_HOVER,
            text_color=Colors.TEXT_PRIMARY,
            font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.TINY_SIZE),
            command=lambda: self._select_files(available_files),
        ).pack(side="left", padx=(0, 4))

        ctk.CTkButton(
            left,
            text="Deselect All",
            width=90,
            height=28,
            corner_radius=Spacing.RADIUS_SM,
            fg_color="transparent",
            hover_color=Colors.BG_HOVER,
            text_color=Colors.TEXT_SECONDARY,
            font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.TINY_SIZE),
            command=self._clear_selection,
        ).pack(side="left")

        right = ctk.CTkFrame(bar, fg_color="transparent")
        right.pack(side="right", padx=Spacing.PAD_SM, pady=6)

        # Sort options dropdown
        ctk.CTkLabel(
            right,
            text="Sort:",
            font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.TINY_SIZE),
            text_color=Colors.TEXT_MUTED,
        ).pack(side="left", padx=(0, 2))

        sort_opt = ctk.CTkOptionMenu(
            right,
            values=["Size (Desc)", "Size (Asc)", "Name (A-Z)", "Name (Z-A)", "Date (Newest)"],
            width=115,
            height=26,
            corner_radius=Spacing.RADIUS_SM,
            fg_color=Colors.BG_TERTIARY,
            button_color=Colors.BG_HOVER,
            button_hover_color=Colors.ACCENT_HOVER,
            text_color=Colors.TEXT_PRIMARY,
            font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.TINY_SIZE),
            command=self._change_sort_mode,
        )
        sort_opt.set(self._sort_mode)
        sort_opt.pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            right,
            text="Export CSV/JSON",
            width=120,
            height=28,
            corner_radius=Spacing.RADIUS_SM,
            fg_color=Colors.BG_TERTIARY,
            hover_color=Colors.BG_HOVER,
            text_color=Colors.ACCENT,
            font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.TINY_SIZE, weight="bold"),
            command=lambda: self._export_data(export_title, available_files),
        ).pack(side="right", padx=(6, 0))

        self._batch_del_btn = ctk.CTkButton(
            right,
            text="Delete Selected (0)",
            height=28,
            corner_radius=Spacing.RADIUS_SM,
            fg_color=Colors.BG_TERTIARY,
            hover_color=Colors.RED,
            text_color="#ffffff",
            font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.TINY_SIZE, weight="bold"),
            state="disabled",
            command=self._confirm_batch_delete,
        )
        self._batch_del_btn.pack(side="right")
        self._update_batch_bar_status()

    def _change_sort_mode(self, mode: str):
        self._sort_mode = mode
        self._refresh_active_list()

    def _sort_file_items(self, items: list[tuple]) -> list[tuple]:
        if not items:
            return items
        m = self._sort_mode
        if m == "Size (Desc)":
            return sorted(items, key=lambda x: x[1], reverse=True)
        elif m == "Size (Asc)":
            return sorted(items, key=lambda x: x[1], reverse=False)
        elif m == "Name (A-Z)":
            return sorted(items, key=lambda x: os.path.basename(x[0]).lower(), reverse=False)
        elif m == "Name (Z-A)":
            return sorted(items, key=lambda x: os.path.basename(x[0]).lower(), reverse=True)
        elif m == "Date (Newest)":
            return sorted(items, key=lambda x: x[2] if len(x) > 2 and isinstance(x[2], (int, float)) else 0, reverse=True)
        return items

    def _preview_file(self, filepath: str):
        FilePreviewDialog(
            self,
            filepath=filepath,
            on_delete=lambda p: self._confirm_delete(p),
            on_open=lambda p: self._open_in_explorer(p),
        )

    def _refresh_active_list(self):
        """Refresh list content of current active view without destroying tab layout."""
        if self._current_view == 0 and self._results[0]:
            self._dup_list.clear()
            self._render_duplicates(self._results[0])
        elif self._current_view == 1 and self._results[1]:
            self._usage_list.clear()
            self._render_disk_usage(self._results[1], self._usage_tab_index)
        elif self._current_view == 2 and self._results[2]:
            self._cleanup_list.clear()
            self._render_cleanup(self._results[2])
        elif self._current_view == 3 and self._results[3]:
            self._search_list.clear()
            self._render_search(self._results[3])

    def _update_checkbox_widgets(self):
        """Update all visible checkbox widgets directly without rebuilding list UI."""
        active_list = None
        if self._current_view == 0:
            active_list = getattr(self, "_dup_list", None)
        elif self._current_view == 1:
            active_list = getattr(self, "_usage_list", None)
        elif self._current_view == 2:
            active_list = getattr(self, "_cleanup_list", None)
        elif self._current_view == 3:
            active_list = getattr(self, "_search_list", None)

        if active_list:
            self._set_checkboxes_in_container(active_list)
        self._update_batch_bar_status()

    def _set_checkboxes_in_container(self, container):
        for child in container.winfo_children():
            if isinstance(child, FileRow):
                child.set_checked(child.filepath in self._selected_files)
            elif isinstance(child, ctk.CTkFrame):
                self._set_checkboxes_in_container(child)

    def _remove_deleted_rows_from_ui(self, deleted_paths: set[str]):
        """Remove specific deleted file rows from UI instantly without re-rendering or clearing the list."""
        active_list = None
        if self._current_view == 0:
            active_list = getattr(self, "_dup_list", None)
        elif self._current_view == 1:
            active_list = getattr(self, "_usage_list", None)
        elif self._current_view == 2:
            active_list = getattr(self, "_cleanup_list", None)
        elif self._current_view == 3:
            active_list = getattr(self, "_search_list", None)

        if not active_list:
            return

        norm_deleted = {os.path.normpath(p) for p in deleted_paths}
        self._destroy_matching_rows(active_list, norm_deleted)
        self._update_batch_bar_status()

    def _destroy_matching_rows(self, container, norm_deleted: set[str]):
        for child in list(container.winfo_children()):
            if hasattr(child, "filepath") and child.filepath:
                if os.path.normpath(child.filepath) in norm_deleted:
                    child.destroy()
            elif isinstance(child, ctk.CTkFrame):
                self._destroy_matching_rows(child, norm_deleted)
                # If a sub-group frame has no remaining FileRow/SizeBar data children, clean it up
                remaining = [
                    c for c in child.winfo_children()
                    if isinstance(c, (FileRow, SizeBar))
                ]
                if not remaining and not isinstance(child, ScrollableList):
                    try:
                        child.destroy()
                    except Exception:
                        pass

    def _select_files(self, filepaths: list[str]):
        for p in filepaths:
            self._selected_files.add(p)
        self._update_checkbox_widgets()

    def _clear_selection(self):
        self._selected_files.clear()
        self._update_checkbox_widgets()

    # ─── Duplicate Finder View ───

    def _build_duplicates_view(self):
        container = ctk.CTkFrame(self._content, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=Spacing.PAD_XL, pady=Spacing.PAD_XL)

        SectionHeader(
            container,
            title="Duplicate Files",
            subtitle="Find identical files taking up extra space",
            action_text="Scan",
            action_command=self._start_duplicate_scan,
        ).pack(fill="x", pady=(0, Spacing.PAD_MD))

        # Extension Filter Bar
        filter_bar = ctk.CTkFrame(container, fg_color="transparent", height=32)
        filter_bar.pack(fill="x", pady=(0, Spacing.PAD_MD))

        ctk.CTkLabel(
            filter_bar,
            text="Filter Extension:",
            font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.SMALL_SIZE),
            text_color=Colors.TEXT_MUTED,
        ).pack(side="left", padx=(0, Spacing.PAD_SM))

        categories = ["All", "Media", "Docs", "Archives", "Code"]
        for cat in categories:
            ctk.CTkButton(
                filter_bar,
                text=cat,
                width=70,
                height=26,
                corner_radius=Spacing.RADIUS_SM,
                fg_color=Colors.ACCENT_MUTED if self._dup_ext_filter == cat else "transparent",
                hover_color=Colors.BG_HOVER,
                text_color=Colors.TEXT_PRIMARY if self._dup_ext_filter == cat else Colors.TEXT_SECONDARY,
                font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.TINY_SIZE),
                command=lambda c=cat: self._set_dup_ext_filter(c),
            ).pack(side="left", padx=2)

        self._dup_list = ScrollableList(container)
        self._dup_list.pack(fill="both", expand=True)

        if self._results[0] and self._results[0].duplicates:
            self._render_with_loading(
                self._dup_list, self._render_duplicates, self._results[0]
            )
        else:
            EmptyState(
                self._dup_list,
                icon_text="🔍",
                title="No scan results yet",
                description="Select a folder and click Scan to find duplicate files.",
            ).pack(fill="both", expand=True)

    def _set_dup_ext_filter(self, cat: str):
        self._dup_ext_filter = cat
        if self._results[0]:
            self._dup_list.clear()
            self._render_duplicates(self._results[0])

    def _start_duplicate_scan(self):
        if not self._scan_target:
            self._pick_folder()
            if not self._scan_target:
                return

        if self._scanner.is_running:
            self._scanner.cancel()
            return

        self._dup_list.clear()
        ctk.CTkLabel(
            self._dup_list,
            text="Scanning...",
            font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.BODY_SIZE),
            text_color=Colors.TEXT_MUTED,
        ).pack(pady=Spacing.PAD_XL)

        self._status_bar.set_status("Scanning for duplicates...")
        self._status_bar.set_indeterminate(True)

        self._scanner.scan_duplicates(
            self._scan_target,
            progress_cb=lambda r, p=-1: self.after(100, self._on_dup_progress, r, p),
            complete_cb=lambda r: self.after(100, self._on_dup_complete, r),
        )

    def _on_dup_progress(self, result: ScanResult, pct: float = -1):
        path = result.current_path
        if len(path) > 70:
            path = "..." + path[-67:]
        status = f"Scanned {result.files_scanned:,} files"
        if pct > 0:
            status += f" ({int(min(pct, 0.99) * 100)}%)"
        self._status_bar.set_status(status, progress=pct)
        self._status_bar.set_count(path)

    def _on_dup_complete(self, result: ScanResult):
        self._results[0] = result
        self._status_bar.set_indeterminate(False)

        total_dupes = sum(len(files) - 1 for files in result.duplicates.values())
        wasted = sum(
            files[0][1] * (len(files) - 1) for files in result.duplicates.values()
        )
        self._status_bar.set_status(
            f"Done: {total_dupes} duplicates found, {format_size(wasted)} wasted"
        )
        self._status_bar.set_count(f"{result.files_scanned:,} files scanned")
        HistoryManager.save("Duplicates", self._scan_target, result)

        self._dup_list.clear()
        if self._current_view == 0:
            self._render_duplicates(result)

    def _render_duplicates(self, result: ScanResult):
        if not result.duplicates:
            EmptyState(
                self._dup_list,
                icon_text="✓",
                title="No duplicates found",
                description=f"Scanned {result.files_scanned:,} files. No identical files detected.",
            ).pack(fill="both", expand=True)
            return

        # Extension filter map
        ext_map = {
            "Media": {"mp4", "mkv", "avi", "mov", "mp3", "flac", "jpg", "jpeg", "png", "gif", "webp"},
            "Docs": {"pdf", "docx", "doc", "xlsx", "pptx", "txt", "csv", "md"},
            "Archives": {"zip", "rar", "7z", "tar", "gz", "iso"},
            "Code": {"py", "js", "html", "css", "json", "cpp", "c", "java", "ts"},
        }

        # Collect duplicates matching filter
        filtered_groups = []
        all_duplicate_files = []

        for h_val, files in result.duplicates.items():
            valid_files = files
            if self._dup_ext_filter in ext_map:
                target_exts = ext_map[self._dup_ext_filter]
                valid_files = [
                    f for f in files if get_file_extension(f[0]) in target_exts
                ]
            if len(valid_files) > 1:
                filtered_groups.append((h_val, valid_files))
                # Add all except 1st to selectable batch duplicates
                for f in valid_files[1:]:
                    all_duplicate_files.append(f[0])

        if not filtered_groups:
            EmptyState(
                self._dup_list,
                icon_text="🔍",
                title=f"No duplicates for filter '{self._dup_ext_filter}'",
                description="Try selecting 'All' to see all duplicate files.",
            ).pack(fill="both", expand=True)
            return

        # Render Batch Action Bar
        self._build_batch_bar(self._dup_list, all_duplicate_files, export_title="Duplicates")

        # Summary
        total_dupes = sum(len(files) - 1 for _, files in filtered_groups)
        total_groups = len(filtered_groups)
        wasted = sum(files[0][1] * (len(files) - 1) for _, files in filtered_groups)

        summary = ctk.CTkFrame(self._dup_list, fg_color=Colors.BG_TERTIARY, corner_radius=Spacing.RADIUS_LG)
        summary.pack(fill="x", pady=(0, Spacing.PAD_LG), padx=2)

        summary_inner = ctk.CTkFrame(summary, fg_color="transparent")
        summary_inner.pack(fill="x", padx=Spacing.PAD_LG, pady=Spacing.PAD_MD)

        stats_data = [
            (f"{total_groups}", "groups"),
            (f"{total_dupes}", "duplicates"),
            (format_size(wasted), "recoverable"),
        ]

        for val, label in stats_data:
            col = ctk.CTkFrame(summary_inner, fg_color="transparent")
            col.pack(side="left", expand=True)
            ctk.CTkLabel(
                col, text=val,
                font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.HEADING_SIZE, weight="bold"),
                text_color=Colors.ACCENT,
            ).pack()
            ctk.CTkLabel(
                col, text=label,
                font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.TINY_SIZE),
                text_color=Colors.TEXT_MUTED,
            ).pack()

        # Groups
        sorted_groups = sorted(
            filtered_groups,
            key=lambda x: x[1][0][1] * (len(x[1]) - 1),
            reverse=True,
        )

        for i, (hash_val, files) in enumerate(sorted_groups[:50]):
            group_frame = ctk.CTkFrame(
                self._dup_list,
                fg_color=Colors.BG_SECONDARY,
                corner_radius=Spacing.RADIUS_MD,
            )
            group_frame.pack(fill="x", pady=(0, Spacing.PAD_SM), padx=2)

            header = ctk.CTkFrame(group_frame, fg_color="transparent")
            header.pack(fill="x", padx=Spacing.PAD_MD, pady=(Spacing.PAD_SM, 0))

            wasted_per_group = files[0][1] * (len(files) - 1)
            ctk.CTkLabel(
                header,
                text=f"Group {i+1}  ·  {len(files)} copies  ·  {format_size(files[0][1])} each  ·  {format_size(wasted_per_group)} wasted",
                font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.SMALL_SIZE),
                text_color=Colors.TEXT_MUTED,
                anchor="w",
            ).pack(side="left")

            for j, (filepath, size, mtime) in enumerate(files):
                is_first = j == 0
                FileRow(
                    group_frame,
                    filepath=filepath,
                    size_text=format_size(size),
                    detail_text="keep (oldest)" if is_first else format_time_ago(mtime),
                    show_checkbox=not is_first,
                    is_checked=(filepath in self._selected_files),
                    on_check=self._on_file_check,
                    on_preview=self._preview_file,
                    on_click=lambda p: self._open_in_explorer(p),
                    on_delete=lambda p: self._confirm_delete(p),
                    show_delete=True,
                    row_color=Colors.ACCENT_MUTED if is_first else None,
                ).pack(fill="x", padx=Spacing.PAD_SM, pady=1)

            ctk.CTkFrame(group_frame, height=Spacing.PAD_SM, fg_color="transparent").pack()

    # ─── Disk Usage View ───

    def _build_disk_usage_view(self):
        container = ctk.CTkFrame(self._content, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=Spacing.PAD_XL, pady=Spacing.PAD_XL)

        SectionHeader(
            container,
            title="Disk Usage",
            subtitle="Visualize what's taking up space",
            action_text="Analyze",
            action_command=self._start_disk_scan,
        ).pack(fill="x", pady=(0, Spacing.PAD_LG))

        tab_frame = ctk.CTkFrame(container, fg_color="transparent", height=36)
        tab_frame.pack(fill="x", pady=(0, Spacing.PAD_MD))

        tab_names = ["Largest Folders", "Largest Files", "By Category", "Visual Treemap"]

        for i, name in enumerate(tab_names):
            is_active = (i == self._usage_tab_index)
            ctk.CTkButton(
                tab_frame,
                text=name,
                width=130,
                height=30,
                corner_radius=Spacing.RADIUS_SM,
                fg_color=Colors.ACCENT_MUTED if is_active else "transparent",
                hover_color=Colors.BG_HOVER,
                text_color=Colors.TEXT_PRIMARY if is_active else Colors.TEXT_SECONDARY,
                font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.SMALL_SIZE),
                command=lambda idx=i: self._switch_usage_tab(idx),
            ).pack(side="left", padx=(0, 4))

        self._usage_list = ScrollableList(container)
        self._usage_list.pack(fill="both", expand=True)

        if self._results[1]:
            self._render_with_loading(
                self._usage_list, self._render_disk_usage, self._results[1], self._usage_tab_index
            )
        else:
            EmptyState(
                self._usage_list,
                icon_text="📊",
                title="No analysis yet",
                description="Select a folder and click Analyze to see disk usage breakdown.",
            ).pack(fill="both", expand=True)

    def _switch_usage_tab(self, tab_idx):
        self._usage_tab_index = tab_idx
        tab_frame = None
        for w in self._content.winfo_children():
            for child in w.winfo_children():
                if isinstance(child, ctk.CTkFrame) and child.cget("height") == 36:
                    tab_frame = child
                    break

        if tab_frame:
            for i, btn in enumerate(tab_frame.winfo_children()):
                if isinstance(btn, ctk.CTkButton):
                    btn.configure(
                        fg_color=Colors.ACCENT_MUTED if i == tab_idx else "transparent",
                        text_color=Colors.TEXT_PRIMARY if i == tab_idx else Colors.TEXT_SECONDARY,
                    )

        if self._results[1]:
            self._usage_list.clear()
            self._render_disk_usage(self._results[1], tab_idx)

    def _start_disk_scan(self):
        if not self._scan_target:
            self._pick_folder()
            if not self._scan_target:
                return

        if self._scanner.is_running:
            self._scanner.cancel()
            return

        self._usage_list.clear()
        ctk.CTkLabel(
            self._usage_list,
            text="Analyzing...",
            font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.BODY_SIZE),
            text_color=Colors.TEXT_MUTED,
        ).pack(pady=Spacing.PAD_XL)

        self._status_bar.set_status("Analyzing disk usage...")
        self._status_bar.set_indeterminate(True)

        self._scanner.scan_disk_usage(
            self._scan_target,
            progress_cb=lambda r, p=-1: self.after(100, self._on_usage_progress, r, p),
            complete_cb=lambda r: self.after(100, self._on_usage_complete, r),
        )

    def _on_usage_progress(self, result: ScanResult, pct: float = -1):
        status = f"Scanned {result.files_scanned:,} files  ·  {format_size(result.total_size)}"
        if pct > 0:
            status += f" ({int(min(pct, 0.99) * 100)}%)"
        self._status_bar.set_status(status, progress=pct)

    def _on_usage_complete(self, result: ScanResult):
        self._results[1] = result
        self._status_bar.set_indeterminate(False)
        self._status_bar.set_status(
            f"Done: {result.files_scanned:,} files, {format_size(result.total_size)} total"
        )
        HistoryManager.save("Disk Usage", self._scan_target, result)

        self._usage_list.clear()
        if self._current_view == 1:
            self._render_disk_usage(result, self._usage_tab_index)

    def _render_disk_usage(self, result: ScanResult, tab: int):
        max_size = result.total_size if result.total_size > 0 else 1

        if tab == 0:
            # Largest folders
            folders = [
                (p, s, d) for p, s, d in result.largest_items if d and p != self._scan_target
            ][:50]

            if not folders:
                EmptyState(
                    self._usage_list, "📁", "No folder data",
                    "No subfolders found in the scanned location.",
                ).pack(fill="both", expand=True)
                return

            for path, size, _ in folders:
                proportion = size / max_size
                rel = os.path.relpath(path, self._scan_target)
                SizeBar(
                    self._usage_list,
                    label=rel,
                    size_text=format_size(size),
                    proportion=proportion,
                    color=self._size_color(proportion),
                    on_click=lambda p=path: self._open_in_explorer(p),
                ).pack(fill="x", pady=1)

        elif tab == 1:
            # Largest files
            raw_files = [(p, s, 0) for p, s, d in result.largest_items if not d][:80]
            sorted_files = self._sort_file_items(raw_files)
            file_paths = [p for p, _, _ in sorted_files]

            if not sorted_files:
                EmptyState(
                    self._usage_list, "📄", "No files found",
                    "No files found in the scanned location.",
                ).pack(fill="both", expand=True)
                return

            self._build_batch_bar(self._usage_list, file_paths, export_title="Largest Files")

            for path, size, _ in sorted_files:
                FileRow(
                    self._usage_list,
                    filepath=path,
                    size_text=format_size(size),
                    detail_text=os.path.dirname(path)[-35:] if len(os.path.dirname(path)) > 35 else os.path.dirname(path),
                    show_checkbox=True,
                    is_checked=(path in self._selected_files),
                    on_check=self._on_file_check,
                    on_preview=self._preview_file,
                    show_delete=True,
                    on_delete=lambda p: self._confirm_delete(p),
                    on_click=lambda p: self._open_in_explorer(p),
                ).pack(fill="x", pady=1)

        elif tab == 2:
            # By category
            if not result.categories:
                EmptyState(
                    self._usage_list, "📦", "No data",
                    "No file categories detected.",
                ).pack(fill="both", expand=True)
                return

            sorted_cats = sorted(
                result.categories.items(),
                key=lambda x: x[1][1],
                reverse=True,
            )

            cat_colors = {
                "Images": "#e0a84e",
                "Videos": "#e05c5c",
                "Audio": "#5b8def",
                "Documents": "#2eb8a6",
                "Archives": "#a07cf0",
                "Code": "#48c78e",
                "Executable": "#f07cbe",
                "Other": "#7a829e",
            }

            for cat_name, (count, cat_size) in sorted_cats:
                proportion = cat_size / max_size
                color = cat_colors.get(cat_name, Colors.ACCENT)

                card = ctk.CTkFrame(self._usage_list, fg_color=Colors.BG_SECONDARY, corner_radius=Spacing.RADIUS_MD)
                card.pack(fill="x", pady=(0, Spacing.PAD_SM), padx=2)

                card_inner = ctk.CTkFrame(card, fg_color="transparent")
                card_inner.pack(fill="x", padx=Spacing.PAD_MD, pady=Spacing.PAD_SM)

                top_line = ctk.CTkFrame(card_inner, fg_color="transparent")
                top_line.pack(fill="x")

                ctk.CTkLabel(
                    top_line,
                    text=f"  {cat_name}",
                    font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.BODY_SIZE, weight="bold"),
                    text_color=Colors.TEXT_PRIMARY,
                ).pack(side="left")

                ctk.CTkLabel(
                    top_line,
                    text=f"{count:,} files  ·  {format_size(cat_size)}",
                    font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.SMALL_SIZE),
                    text_color=Colors.TEXT_MUTED,
                ).pack(side="right")

                bar = ctk.CTkProgressBar(
                    card_inner,
                    height=6,
                    corner_radius=3,
                    fg_color=Colors.BG_TERTIARY,
                    progress_color=color,
                )
                bar.pack(fill="x", pady=(Spacing.PAD_XS, 0))
                bar.set(min(proportion, 1.0))

        elif tab == 3:
            # Visual Treemap
            items = [(p, s, os.path.basename(p)) for p, s, d in result.largest_items if s > 0][:40]
            if not items:
                EmptyState(
                    self._usage_list, "🎨", "No treemap data",
                    "Scan data is empty.",
                ).pack(fill="both", expand=True)
                return

            treemap_frame = ctk.CTkFrame(self._usage_list, fg_color=Colors.BG_SECONDARY, height=450, corner_radius=Spacing.RADIUS_MD)
            treemap_frame.pack(fill="both", expand=True, padx=2, pady=2)
            treemap_frame.pack_propagate(False)

            canvas = TreemapCanvas(
                treemap_frame,
                items=items,
                on_click=lambda p: self._open_in_explorer(p),
                on_hover=lambda msg: self._status_bar.set_status(msg),
            )
            canvas.pack(fill="both", expand=True, padx=4, pady=4)

    def _size_color(self, proportion: float) -> str:
        if proportion > 0.2:
            return Colors.RED
        elif proportion > 0.08:
            return Colors.AMBER
        elif proportion > 0.03:
            return Colors.ACCENT
        return Colors.TEXT_MUTED

    # ─── Cleanup View ───

    def _build_cleanup_view(self):
        container = ctk.CTkFrame(self._content, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=Spacing.PAD_XL, pady=Spacing.PAD_XL)

        SectionHeader(
            container,
            title="Cleanup Suggestions",
            subtitle="Files that are likely safe to delete to free up space",
            action_text="Find Waste",
            action_command=self._start_cleanup_scan,
        ).pack(fill="x", pady=(0, Spacing.PAD_LG))

        self._cleanup_list = ScrollableList(container)
        self._cleanup_list.pack(fill="both", expand=True)

        if self._results[2]:
            self._render_with_loading(
                self._cleanup_list, self._render_cleanup, self._results[2]
            )
        else:
            EmptyState(
                self._cleanup_list,
                icon_text="🧹",
                title="No cleanup scan yet",
                description="Select a folder and click Find Waste to discover unnecessary files.",
            ).pack(fill="both", expand=True)

    def _start_cleanup_scan(self):
        if not self._scan_target:
            self._pick_folder()
            if not self._scan_target:
                return

        if self._scanner.is_running:
            self._scanner.cancel()
            return

        self._cleanup_list.clear()
        ctk.CTkLabel(
            self._cleanup_list,
            text="Scanning for waste...",
            font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.BODY_SIZE),
            text_color=Colors.TEXT_MUTED,
        ).pack(pady=Spacing.PAD_XL)

        self._status_bar.set_status("Scanning for cleanup suggestions...")
        self._status_bar.set_indeterminate(True)

        self._scanner.scan_cleanup(
            self._scan_target,
            progress_cb=lambda r, p=-1: self.after(100, self._on_cleanup_progress, r, p),
            complete_cb=lambda r: self.after(100, self._on_cleanup_complete, r),
        )

    def _on_cleanup_progress(self, result: ScanResult, pct: float = -1):
        status = f"Scanned {result.files_scanned:,} files"
        if pct > 0:
            status += f" ({int(min(pct, 0.99) * 100)}%)"
        self._status_bar.set_status(status, progress=pct)

    def _on_cleanup_complete(self, result: ScanResult):
        self._results[2] = result
        self._status_bar.set_indeterminate(False)
        total_reclaimable = sum(s for _, s, _ in result.cleanup_suggestions)
        self._status_bar.set_status(
            f"Done: {len(result.cleanup_suggestions)} items found, {format_size(total_reclaimable)} reclaimable"
        )
        HistoryManager.save("Cleanup", self._scan_target, result)

        self._cleanup_list.clear()
        if self._current_view == 2:
            self._render_cleanup(result)

    def _render_cleanup(self, result: ScanResult):
        if not result.cleanup_suggestions:
            EmptyState(
                self._cleanup_list,
                icon_text="✨",
                title="Clean system!",
                description="No obvious waste or temp files found in the scanned folder.",
            ).pack(fill="both", expand=True)
            return

        sorted_cleanup = self._sort_file_items(result.cleanup_suggestions)
        file_paths = [p for p, _, _ in sorted_cleanup]
        self._build_batch_bar(self._cleanup_list, file_paths, export_title="Cleanup Suggestions")

        total_size = sum(size for _, size, _ in sorted_cleanup)

        summary = ctk.CTkFrame(self._cleanup_list, fg_color=Colors.BG_TERTIARY, corner_radius=Spacing.RADIUS_LG)
        summary.pack(fill="x", pady=(0, Spacing.PAD_LG), padx=2)

        summary_inner = ctk.CTkFrame(summary, fg_color="transparent")
        summary_inner.pack(fill="x", padx=Spacing.PAD_LG, pady=Spacing.PAD_MD)

        col1 = ctk.CTkFrame(summary_inner, fg_color="transparent")
        col1.pack(side="left", expand=True)
        ctk.CTkLabel(
            col1, text=f"{len(sorted_cleanup)}",
            font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.HEADING_SIZE, weight="bold"),
            text_color=Colors.ACCENT,
        ).pack()
        ctk.CTkLabel(
            col1, text="files to clean",
            font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.TINY_SIZE),
            text_color=Colors.TEXT_MUTED,
        ).pack()

        col2 = ctk.CTkFrame(summary_inner, fg_color="transparent")
        col2.pack(side="left", expand=True)
        ctk.CTkLabel(
            col2, text=format_size(total_size),
            font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.HEADING_SIZE, weight="bold"),
            text_color=Colors.GREEN,
        ).pack()
        ctk.CTkLabel(
            col2, text="space reclaimable",
            font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.TINY_SIZE),
            text_color=Colors.TEXT_MUTED,
        ).pack()

        for filepath, size, reason in sorted_cleanup:
            FileRow(
                self._cleanup_list,
                filepath=filepath,
                size_text=format_size(size),
                detail_text=reason,
                show_checkbox=True,
                is_checked=(filepath in self._selected_files),
                on_check=self._on_file_check,
                on_preview=self._preview_file,
                show_delete=True,
                on_delete=lambda p: self._confirm_delete(p),
                on_click=lambda p: self._open_in_explorer(p),
            ).pack(fill="x", pady=1)

    # ─── Search View ───

    def _build_search_view(self):
        container = ctk.CTkFrame(self._content, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=Spacing.PAD_XL, pady=Spacing.PAD_XL)

        SectionHeader(
            container,
            title="File Search",
            subtitle="Search across all files in target folder",
        ).pack(fill="x", pady=(0, Spacing.PAD_MD))

        search_bar = ctk.CTkFrame(container, fg_color="transparent")
        search_bar.pack(fill="x", pady=(0, Spacing.PAD_LG))

        self._search_input = ctk.CTkEntry(
            search_bar,
            placeholder_text="Enter filename or extension (e.g., .mp4, project, report...)",
            height=38,
            corner_radius=Spacing.RADIUS_MD,
            fg_color=Colors.BG_SECONDARY,
            border_color=Colors.BORDER,
            font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.BODY_SIZE),
        )
        self._search_input.pack(side="left", fill="x", expand=True, padx=(0, Spacing.PAD_SM))
        self._search_input.bind("<Return>", lambda e: self._start_search())

        ctk.CTkButton(
            search_bar,
            text="Search",
            width=100,
            height=38,
            corner_radius=Spacing.RADIUS_MD,
            fg_color=Colors.ACCENT,
            hover_color=Colors.ACCENT_HOVER,
            text_color=Colors.BG_PRIMARY,
            font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.BODY_SIZE, weight="bold"),
            command=self._start_search,
        ).pack(side="right")

        self._search_list = ScrollableList(container)
        self._search_list.pack(fill="both", expand=True)

        if self._results[3]:
            self._render_with_loading(
                self._search_list, self._render_search, self._results[3]
            )
        else:
            EmptyState(
                self._search_list,
                icon_text="🔎",
                title="Search files",
                description="Type a search query and click Search.",
            ).pack(fill="both", expand=True)

    def _start_search(self):
        query = self._search_input.get().strip()
        if not query:
            return

        if not self._scan_target:
            self._pick_folder()
            if not self._scan_target:
                return

        self._search_query = query
        self._search_list.clear()
        ctk.CTkLabel(
            self._search_list,
            text=f"Searching for '{query}'...",
            font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.BODY_SIZE),
            text_color=Colors.TEXT_MUTED,
        ).pack(pady=Spacing.PAD_XL)

        self._status_bar.set_status(f"Searching for '{query}'...")
        self._status_bar.set_indeterminate(True)

        self._scanner.search_files(
            self._scan_target,
            query=query,
            progress_cb=lambda r, p=-1: self.after(100, self._on_search_progress, r, p),
            complete_cb=lambda r: self.after(100, self._on_search_complete, r),
        )

    def _on_search_progress(self, result: ScanResult, pct: float = -1):
        status = f"Found {len(result.search_results)} matches ({result.files_scanned:,} scanned)"
        if pct > 0:
            status += f" ({int(min(pct, 0.99) * 100)}%)"
        self._status_bar.set_status(status, progress=pct)

    def _on_search_complete(self, result: ScanResult):
        self._results[3] = result
        self._status_bar.set_indeterminate(False)
        self._status_bar.set_status(
            f"Done: {len(result.search_results)} files found matching '{self._search_query}'"
        )

        self._search_list.clear()
        if self._current_view == 3:
            self._render_search(result)

    def _render_search(self, result: ScanResult):
        if not result.search_results:
            EmptyState(
                self._search_list,
                icon_text="∅",
                title="No results",
                description=f"No matching files in {result.files_scanned:,} items.",
            ).pack(fill="both", expand=True)
            return

        sorted_results = self._sort_file_items(result.search_results)
        file_paths = [p for p, _, _ in sorted_results]

        self._build_batch_bar(self._search_list, file_paths, export_title=f"Search '{self._search_query}'")

        count_label = ctk.CTkLabel(
            self._search_list,
            text=f"{len(sorted_results)} results found",
            font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.SMALL_SIZE),
            text_color=Colors.TEXT_MUTED,
            anchor="w",
        )
        count_label.pack(anchor="w", pady=(0, Spacing.PAD_SM))

        for filepath, size, mtime in sorted_results[:200]:
            is_dir = os.path.isdir(filepath)
            FileRow(
                self._search_list,
                filepath=filepath,
                size_text=format_size(size) if not is_dir else "DIR",
                detail_text=format_time_ago(mtime) if mtime > 0 else "",
                show_checkbox=True,
                is_checked=(filepath in self._selected_files),
                on_check=self._on_file_check,
                on_preview=self._preview_file,
                show_delete=True,
                on_delete=lambda p: self._confirm_delete(p),
                on_click=lambda p: self._open_in_explorer(p),
            ).pack(fill="x", pady=1)

    # ─── History View ───

    def _build_history_view(self):
        container = ctk.CTkFrame(self._content, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=Spacing.PAD_XL, pady=Spacing.PAD_XL)

        SectionHeader(
            container,
            title="Scan History",
            subtitle="Saved scan reports from previous sessions",
        ).pack(fill="x", pady=(0, Spacing.PAD_LG))

        history_list = ScrollableList(container)
        history_list.pack(fill="both", expand=True)

        records = HistoryManager.load_all()
        if not records:
            EmptyState(
                history_list,
                icon_text="📜",
                title="No history yet",
                description="Scan reports will automatically appear here.",
            ).pack(fill="both", expand=True)
            return

        for rec in records:
            card = ctk.CTkFrame(history_list, fg_color=Colors.BG_SECONDARY, corner_radius=Spacing.RADIUS_MD)
            card.pack(fill="x", pady=(0, Spacing.PAD_SM), padx=2)

            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="x", padx=Spacing.PAD_MD, pady=Spacing.PAD_MD)

            left = ctk.CTkFrame(inner, fg_color="transparent")
            left.pack(side="left", fill="x", expand=True)

            title_text = f"{rec.get('scan_type', 'Scan')}  ·  {rec.get('root_path', '')}"
            ctk.CTkLabel(
                left,
                text=title_text,
                font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.BODY_SIZE, weight="bold"),
                text_color=Colors.TEXT_PRIMARY,
                anchor="w",
            ).pack(anchor="w")

            detail_text = f"Date: {rec.get('date_str')}  ·  Files: {rec.get('total_files', 0):,}  ·  Size: {format_size(rec.get('total_size', 0))}"
            ctk.CTkLabel(
                left,
                text=detail_text,
                font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.SMALL_SIZE),
                text_color=Colors.TEXT_MUTED,
                anchor="w",
            ).pack(anchor="w", pady=(2, 0))

            ctk.CTkButton(
                inner,
                text="Load Report",
                width=110,
                height=30,
                corner_radius=Spacing.RADIUS_SM,
                fg_color=Colors.ACCENT,
                hover_color=Colors.ACCENT_HOVER,
                text_color=Colors.BG_PRIMARY,
                font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.TINY_SIZE, weight="bold"),
                command=lambda r=rec: self._load_history_report(r),
            ).pack(side="right", padx=(Spacing.PAD_MD, 0))

    def _load_history_report(self, record: dict):
        scan_type = record.get("scan_type", "")
        self._scan_target = record.get("root_path", "")
        display = self._scan_target if len(self._scan_target) < 35 else "..." + self._scan_target[-32:]
        self._path_label.configure(text=display)

        result_dict = record.get("result_dict", {})
        result = ScanResult.from_dict(result_dict)

        if scan_type == "Duplicates":
            self._results[0] = result
            self._show_view(0)
        elif scan_type == "Disk Usage":
            self._results[1] = result
            self._show_view(1)
        elif scan_type == "Cleanup":
            self._results[2] = result
            self._show_view(2)

        self._status_bar.set_status(f"Loaded history report for '{scan_type}'")

    # ─── Shared Actions & Deletion Engine ───

    def _open_in_explorer(self, filepath: str):
        """Open file location in Windows Explorer."""
        try:
            filepath = os.path.normpath(filepath)
            if os.path.isdir(filepath):
                os.startfile(filepath)
            else:
                subprocess.Popen(f'explorer /select,"{filepath}"')
        except Exception as e:
            self._status_bar.set_status(f"Error opening location: {e}")

    def _confirm_delete(self, filepath: str):
        """Show confirmation dialog before deleting."""
        name = os.path.basename(filepath)
        is_dir = os.path.isdir(filepath)
        item_type = "folder" if is_dir else "file"

        ConfirmDialog(
            self,
            title=f"Delete {item_type}?",
            message=f'Move "{name}" to Recycle Bin? This can be undone from the Recycle Bin.',
            on_confirm=lambda: self._do_delete(filepath),
        )

    def _do_delete(self, filepath: str):
        """Send file/folder to Recycle Bin with direct OS removal fallback."""
        from send2trash import send2trash
        import shutil

        norm_path = os.path.normpath(filepath)
        filename = os.path.basename(filepath)

        # Check if file exists
        if not os.path.exists(norm_path) and not os.path.islink(norm_path):
            msg = f"Item no longer exists: {filename}"
            for res in self._results.values():
                if res:
                    res.purge_file(filepath)
            self._selected_files.discard(filepath)
            self._status_bar.set_status(msg)
            self._refresh_active_list()
            return

        success = False
        status_msg = ""

        # Attempt 1: send2trash
        try:
            send2trash(norm_path)
            success = True
            status_msg = f"Moved to Recycle Bin: {filename}"
        except Exception:
            pass

        # Attempt 2: Fallback to direct OS removal (for items in $Recycle.Bin or path quirks)
        if not success:
            try:
                if os.path.isdir(norm_path) and not os.path.islink(norm_path):
                    shutil.rmtree(norm_path)
                else:
                    os.remove(norm_path)
                success = True
                status_msg = f"Permanently deleted: {filename}"
            except PermissionError:
                status_msg = f"System file protected by Windows OS ({filename})"
            except Exception as e:
                status_msg = f"Error deleting {filename}: {e}"

        deleted_set = set()
        if success:
            for res in self._results.values():
                if res:
                    res.purge_file(filepath)
            self._selected_files.discard(filepath)
            deleted_set.add(filepath)

        self._status_bar.set_status(status_msg)
        if deleted_set:
            self._remove_deleted_rows_from_ui(deleted_set)

    def _confirm_batch_delete(self):
        """Show confirmation dialog for batch delete."""
        if not self._selected_files:
            return

        count = len(self._selected_files)
        total_size = 0
        for path in list(self._selected_files):
            try:
                if os.path.isfile(path):
                    total_size += os.path.getsize(path)
            except Exception:
                pass

        ConfirmDialog(
            self,
            title=f"Delete {count} Selected Items?",
            message=f'Move {count} selected files ({format_size(total_size)}) to Recycle Bin?\nThis can be undone from the Recycle Bin.',
            on_confirm=self._do_batch_delete,
        )

    def _do_batch_delete(self):
        """Send all selected files to Recycle Bin with fallback direct removal."""
        from send2trash import send2trash
        import shutil

        deleted_count = 0
        failed_count = 0
        deleted_set = set()

        for path in list(self._selected_files):
            norm_path = os.path.normpath(path)
            deleted = False

            if not os.path.exists(norm_path) and not os.path.islink(norm_path):
                deleted = True
            else:
                # Attempt 1: send2trash
                try:
                    send2trash(norm_path)
                    deleted = True
                except Exception:
                    pass

                # Attempt 2: Direct removal fallback
                if not deleted:
                    try:
                        if os.path.isdir(norm_path) and not os.path.islink(norm_path):
                            shutil.rmtree(norm_path)
                        else:
                            os.remove(norm_path)
                        deleted = True
                    except Exception:
                        pass

            if deleted:
                for res in self._results.values():
                    if res:
                        res.purge_file(path)
                deleted_set.add(path)
                deleted_count += 1
            else:
                failed_count += 1

        self._selected_files.clear()
        msg = f"Deleted {deleted_count} items"
        if failed_count > 0:
            msg += f" ({failed_count} protected OS items skipped)"
        self._status_bar.set_status(msg)

        # Remove deleted rows in-place instantly without rebuilding list UI
        if deleted_set:
            self._remove_deleted_rows_from_ui(deleted_set)

    def _export_data(self, title: str, file_paths: list[str]):
        """Export list of files to CSV or JSON."""
        if not file_paths:
            self._status_bar.set_status("No data available to export.")
            return

        save_path = filedialog.asksaveasfilename(
            title=f"Export {title}",
            defaultextension=".csv",
            filetypes=[("CSV File", "*.csv"), ("JSON File", "*.json")],
        )
        if not save_path:
            return

        try:
            records = []
            for p in file_paths:
                try:
                    sz = os.path.getsize(p) if os.path.isfile(p) else 0
                    mtime = format_timestamp(os.path.getmtime(p)) if os.path.exists(p) else ""
                except Exception:
                    sz, mtime = 0, ""
                records.append({
                    "filepath": p,
                    "filename": os.path.basename(p),
                    "size_bytes": sz,
                    "size_formatted": format_size(sz),
                    "modified_time": mtime,
                })

            if save_path.endswith(".json"):
                with open(save_path, "w", encoding="utf-8") as f:
                    json.dump(records, f, indent=2)
            else:
                with open(save_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=["filename", "size_formatted", "size_bytes", "modified_time", "filepath"])
                    writer.writeheader()
                    writer.writerows(records)

            self._status_bar.set_status(f"Exported successfully to {os.path.basename(save_path)}")
        except Exception as e:
            self._status_bar.set_status(f"Export failed: {e}")

    def _render_with_loading(self, scroll_list, render_fn, *args):
        """Show a loading indicator, then render results in the next frame."""
        scroll_list.clear()
        loading = ctk.CTkLabel(
            scroll_list,
            text="Loading results...",
            font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.BODY_SIZE),
            text_color=Colors.TEXT_MUTED,
        )
        loading.pack(pady=Spacing.PAD_XL)
        self._status_bar.set_status("Loading cached results...")
        self._status_bar.set_indeterminate(True)

        def do_render():
            scroll_list.clear()
            render_fn(*args)
            self._status_bar.set_indeterminate(False)
            self._status_bar.set_status("Ready")

        self.after(80, do_render)


def main():
    app = DiskSenseApp()
    app.mainloop()


if __name__ == "__main__":
    main()
