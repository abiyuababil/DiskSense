"""
DiskSense - Reusable UI Components
Styled widgets built on CustomTkinter.
"""

import os
import customtkinter as ctk
from theme import Colors, Fonts, Spacing
from utils import get_file_extension, format_size, format_timestamp


class SidebarButton(ctk.CTkButton):
    """Navigation button for the sidebar."""

    def __init__(self, master, text, icon_text="", active=False, **kwargs):
        self._is_active = active
        super().__init__(
            master,
            text=f"  {icon_text}  {text}" if icon_text else f"  {text}",
            anchor="w",
            height=40,
            corner_radius=Spacing.RADIUS_MD,
            font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.BODY_SIZE, weight="bold" if active else "normal"),
            fg_color=Colors.ACCENT_MUTED if active else "transparent",
            hover_color=Colors.BG_HOVER,
            text_color=Colors.TEXT_PRIMARY if active else Colors.TEXT_SECONDARY,
            **kwargs,
        )

    def set_active(self, active: bool):
        self._is_active = active
        self.configure(
            fg_color=Colors.ACCENT_MUTED if active else "transparent",
            text_color=Colors.TEXT_PRIMARY if active else Colors.TEXT_SECONDARY,
            font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.BODY_SIZE, weight="bold" if active else "normal"),
        )


class StatusBar(ctk.CTkFrame):
    """Bottom status bar showing scan progress."""

    def __init__(self, master, **kwargs):
        super().__init__(master, height=32, corner_radius=0, fg_color=Colors.BG_SECONDARY, **kwargs)

        self._status_label = ctk.CTkLabel(
            self,
            text="Ready",
            font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.SMALL_SIZE),
            text_color=Colors.TEXT_SECONDARY,
            anchor="w",
        )
        self._status_label.pack(side="left", padx=Spacing.PAD_MD)

        self._progress = ctk.CTkProgressBar(
            self,
            width=160,
            height=6,
            corner_radius=3,
            fg_color=Colors.BG_TERTIARY,
            progress_color=Colors.ACCENT,
        )
        self._progress.pack(side="right", padx=Spacing.PAD_MD)
        self._progress.set(0)

        self._count_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(family=Fonts.MONO, size=Fonts.TINY_SIZE),
            text_color=Colors.TEXT_MUTED,
            anchor="e",
        )
        self._count_label.pack(side="right", padx=Spacing.PAD_SM)

    def set_status(self, text: str, progress: float = -1):
        self._status_label.configure(text=text)
        if progress >= 0:
            self._progress.set(min(progress, 1.0))

    def set_count(self, text: str):
        self._count_label.configure(text=text)

    def set_indeterminate(self, active: bool):
        if active:
            self._progress.configure(mode="indeterminate")
            self._progress.start()
        else:
            self._progress.stop()
            self._progress.configure(mode="determinate")
            self._progress.set(0)


class FileRow(ctk.CTkFrame):
    """A single row representing a file in a list with optional selection checkbox and delete button."""

    def __init__(self, master, filepath, size_text, detail_text="",
                 on_click=None, on_delete=None, show_delete=False,
                 show_checkbox=False, is_checked=False, on_check=None,
                 on_preview=None, row_color=None, **kwargs):
        super().__init__(
            master,
            height=40,
            corner_radius=Spacing.RADIUS_SM,
            fg_color=row_color or "transparent",
            **kwargs,
        )
        self.filepath = filepath
        self._base_color = row_color or "transparent"
        self._on_click = on_click
        self._on_delete = on_delete

        self.pack_propagate(False)

        # Checkbox (leftmost)
        self._chk = None
        if show_checkbox:
            self._chk_var = ctk.BooleanVar(value=is_checked)
            self._chk = ctk.CTkCheckBox(
                self,
                text="",
                width=24,
                height=24,
                checkbox_width=18,
                checkbox_height=18,
                border_width=2,
                corner_radius=4,
                fg_color=Colors.ACCENT,
                hover_color=Colors.ACCENT_HOVER,
                variable=self._chk_var,
                command=lambda: on_check(filepath, self._chk_var.get()) if on_check else None,
            )
            self._chk.pack(side="left", padx=(Spacing.PAD_SM, 0))

        # 1. Delete button (paling kanan)
        self._del_btn = None
        if show_delete and on_delete:
            self._del_btn = ctk.CTkButton(
                self,
                text="🗑️",
                width=34,
                height=26,
                corner_radius=Spacing.RADIUS_SM,
                fg_color=Colors.RED_BG,
                hover_color=Colors.RED,
                text_color="#ffffff",
                font=ctk.CTkFont(size=13),
                command=lambda: on_delete(filepath),
            )
            self._del_btn.pack(side="right", padx=(Spacing.PAD_XS, Spacing.PAD_SM))

        # 2. Preview button (sebelah kiri Delete)
        self._prev_btn = None
        if on_preview:
            self._prev_btn = ctk.CTkButton(
                self,
                text="👁️",
                width=34,
                height=26,
                corner_radius=Spacing.RADIUS_SM,
                fg_color=Colors.BG_TERTIARY,
                hover_color=Colors.BG_HOVER,
                text_color=Colors.TEXT_PRIMARY,
                font=ctk.CTkFont(size=13),
                command=lambda: on_preview(filepath),
            )
            self._prev_btn.pack(side="right", padx=(Spacing.PAD_XS, Spacing.PAD_XS))

        # 3. Size label (sebelah kiri Preview)
        self._size_lbl = ctk.CTkLabel(
            self,
            text=size_text,
            font=ctk.CTkFont(family=Fonts.MONO, size=Fonts.SMALL_SIZE),
            text_color=Colors.ACCENT,
            width=85,
            anchor="e",
        )
        self._size_lbl.pack(side="right", padx=(Spacing.PAD_SM, Spacing.PAD_SM))

        # 4. Detail / Location text (sebelah kiri Size)
        self._detail_lbl = None
        if detail_text:
            self._detail_lbl = ctk.CTkLabel(
                self,
                text=detail_text,
                font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.SMALL_SIZE),
                text_color=Colors.TEXT_MUTED,
                width=220,
                anchor="e",
            )
            self._detail_lbl.pack(side="right", padx=(Spacing.PAD_SM, Spacing.PAD_SM))

        # 5. Filename (left, expands - packed LAST so right columns retain fixed width & alignment)
        name = filepath.split("\\")[-1] if "\\" in filepath else filepath.split("/")[-1]
        self._name_lbl = ctk.CTkLabel(
            self,
            text=name,
            font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.BODY_SIZE),
            text_color=Colors.TEXT_PRIMARY,
            anchor="w",
        )
        self._name_lbl.pack(side="left", padx=(Spacing.PAD_MD, Spacing.PAD_SM), fill="x", expand=True)

        # Hover effect on the whole row
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

        # Click: bind to frame + labels (skip checkbox & delete button)
        if on_click:
            self.configure(cursor="hand2")
            self.bind("<Button-1>", lambda e: on_click(filepath))
            for w in [self._name_lbl, self._detail_lbl, self._size_lbl]:
                if w:
                    w.bind("<Button-1>", lambda e: on_click(filepath))
                    w.configure(cursor="hand2")

    def set_checked(self, checked: bool):
        """Set the checkbox state programmatically."""
        if hasattr(self, "_chk_var") and self._chk_var:
            self._chk_var.set(checked)

    def _on_enter(self, event):
        self.configure(fg_color=Colors.BG_HOVER)

    def _on_leave(self, event):
        self.configure(fg_color=self._base_color)


class SectionHeader(ctk.CTkFrame):
    """Section header with title and optional action button."""

    def __init__(self, master, title, subtitle="", action_text="", action_command=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        left = ctk.CTkFrame(self, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            left,
            text=title,
            font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.HEADING_SIZE, weight="bold"),
            text_color=Colors.TEXT_PRIMARY,
            anchor="w",
        ).pack(anchor="w")

        if subtitle:
            ctk.CTkLabel(
                left,
                text=subtitle,
                font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.SMALL_SIZE),
                text_color=Colors.TEXT_MUTED,
                anchor="w",
            ).pack(anchor="w", pady=(2, 0))

        if action_text and action_command:
            ctk.CTkButton(
                self,
                text=action_text,
                width=120,
                height=32,
                corner_radius=Spacing.RADIUS_MD,
                fg_color=Colors.ACCENT,
                hover_color=Colors.ACCENT_HOVER,
                text_color=Colors.BG_PRIMARY,
                font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.SMALL_SIZE, weight="bold"),
                command=action_command,
            ).pack(side="right")


class EmptyState(ctk.CTkFrame):
    """Empty state placeholder."""

    def __init__(self, master, icon_text, title, description, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.place(relx=0.5, rely=0.4, anchor="center")

        ctk.CTkLabel(
            content,
            text=icon_text,
            font=ctk.CTkFont(size=48),
            text_color=Colors.TEXT_MUTED,
        ).pack(pady=(0, Spacing.PAD_MD))

        ctk.CTkLabel(
            content,
            text=title,
            font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.SUBHEADING_SIZE, weight="bold"),
            text_color=Colors.TEXT_SECONDARY,
        ).pack(pady=(0, Spacing.PAD_SM))

        ctk.CTkLabel(
            content,
            text=description,
            font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.BODY_SIZE),
            text_color=Colors.TEXT_MUTED,
            wraplength=300,
        ).pack()


class SizeBar(ctk.CTkFrame):
    """Horizontal bar showing proportion (for disk usage visualization)."""

    def __init__(self, master, label, size_text, proportion, color=None, on_click=None, filepath="", **kwargs):
        super().__init__(master, height=32, fg_color="transparent", **kwargs)
        self.pack_propagate(False)
        self.filepath = filepath
        self._on_click = on_click

        # Label
        lbl = ctk.CTkLabel(
            self,
            text=label,
            font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.BODY_SIZE),
            text_color=Colors.TEXT_PRIMARY,
            anchor="w",
        )
        lbl.pack(side="left", padx=(Spacing.PAD_MD, Spacing.PAD_SM), fill="x", expand=True)

        # Size text (rightmost)
        ctk.CTkLabel(
            self,
            text=size_text,
            font=ctk.CTkFont(family=Fonts.MONO, size=Fonts.SMALL_SIZE),
            text_color=Colors.ACCENT,
            width=80,
            anchor="e",
        ).pack(side="right", padx=Spacing.PAD_MD)

        # Progress bar (fixed uniform width so all tracks align perfectly)
        bar = ctk.CTkProgressBar(
            self,
            width=260,
            height=8,
            corner_radius=4,
            fg_color=Colors.BG_TERTIARY,
            progress_color=color or Colors.ACCENT,
        )
        bar.pack(side="right", padx=Spacing.PAD_SM)
        bar.set(min(proportion, 1.0))

        if on_click:
            self.configure(cursor="hand2")
            self.bind("<Enter>", lambda e: self.configure(fg_color=Colors.BG_HOVER))
            self.bind("<Leave>", lambda e: self.configure(fg_color="transparent"))
            self.bind("<Button-1>", lambda e: on_click())
            for child in self.winfo_children():
                child.bind("<Button-1>", lambda e: on_click())
                try:
                    child.configure(cursor="hand2")
                except Exception:
                    pass


class ConfirmDialog(ctk.CTkToplevel):
    """Confirmation dialog for delete actions."""

    def __init__(self, master, title, message, on_confirm, dangerous=True):
        super().__init__(master)
        self.title(title)
        self.geometry("420x200")
        self.resizable(False, False)
        self.configure(fg_color=Colors.BG_PRIMARY)
        self.transient(master)
        self.grab_set()

        # Center on parent
        self.update_idletasks()
        x = master.winfo_rootx() + (master.winfo_width() - 420) // 2
        y = master.winfo_rooty() + (master.winfo_height() - 200) // 2
        self.geometry(f"+{x}+{y}")

        # Content
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=Spacing.PAD_XL, pady=Spacing.PAD_XL)

        ctk.CTkLabel(
            content,
            text=title,
            font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.SUBHEADING_SIZE, weight="bold"),
            text_color=Colors.TEXT_PRIMARY,
            anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            content,
            text=message,
            font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.BODY_SIZE),
            text_color=Colors.TEXT_SECONDARY,
            wraplength=370,
            anchor="w",
            justify="left",
        ).pack(anchor="w", pady=(Spacing.PAD_SM, Spacing.PAD_LG))

        # Buttons
        btn_frame = ctk.CTkFrame(content, fg_color="transparent")
        btn_frame.pack(fill="x", side="bottom")

        ctk.CTkButton(
            btn_frame,
            text="Cancel",
            width=100,
            height=34,
            corner_radius=Spacing.RADIUS_MD,
            fg_color=Colors.BG_TERTIARY,
            hover_color=Colors.BG_HOVER,
            text_color=Colors.TEXT_SECONDARY,
            font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.BODY_SIZE),
            command=self.destroy,
        ).pack(side="right", padx=(Spacing.PAD_SM, 0))

        confirm_color = Colors.RED if dangerous else Colors.ACCENT
        confirm_hover = Colors.RED_HOVER if dangerous else Colors.ACCENT_HOVER

        def _do_confirm_click():
            try:
                self.grab_release()
            except Exception:
                pass
            self.destroy()
            master.update_idletasks()
            if on_confirm:
                on_confirm()

        ctk.CTkButton(
            btn_frame,
            text="Delete" if dangerous else "Confirm",
            width=100,
            height=34,
            corner_radius=Spacing.RADIUS_MD,
            fg_color=confirm_color,
            hover_color=confirm_hover,
            text_color="#ffffff",
            font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.BODY_SIZE, weight="bold"),
            command=_do_confirm_click,
        ).pack(side="right")

        self.bind("<Escape>", lambda e: self.destroy())
        self.focus_set()


class TreemapCanvas(ctk.CTkCanvas):
    """Canvas widget that renders a visual treemap of disk usage."""

    PALETTE = [
        "#1e3a8a", "#1e40af", "#1d4ed8", "#2563eb",
        "#065f46", "#047857", "#059669", "#10b981",
        "#7c2d12", "#9a3412", "#c2410c", "#ea580c",
        "#581c87", "#6b21a8", "#7e22ce", "#9333ea",
        "#374151", "#4b5563", "#6b7280", "#1f2937",
    ]

    def __init__(self, master, items, on_click=None, on_hover=None, **kwargs):
        super().__init__(
            master,
            bg=Colors.BG_SECONDARY,
            highlightthickness=0,
            **kwargs,
        )
        self.items = items  # list of (path, size, name)
        self.on_click = on_click
        self.on_hover = on_hover
        self._rects = []

        self.bind("<Configure>", lambda e: self.render())
        self.bind("<Motion>", self._handle_motion)
        self.bind("<Button-1>", self._handle_click)

    def set_items(self, items):
        self.items = items
        self.render()

    def render(self):
        self.delete("all")
        self._rects.clear()

        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 10 or h <= 10 or not self.items:
            return

        total_size = sum(size for _, size, _ in self.items)
        if total_size <= 0:
            return

        sorted_items = sorted(self.items, key=lambda x: x[1], reverse=True)[:50]
        self._partition(sorted_items, 0, 0, w, h, sum(s for _, s, _ in sorted_items))

    def _partition(self, items, x, y, w, h, total):
        if not items or w <= 2 or h <= 2 or total <= 0:
            return

        if len(items) == 1:
            path, size, name = items[0]
            idx = abs(hash(path)) % len(self.PALETTE)
            color = self.PALETTE[idx]

            rect_id = self.create_rectangle(
                x + 1, y + 1, x + w - 1, y + h - 1,
                fill=color, outline=Colors.BG_PRIMARY, width=2
            )

            if w > 50 and h > 28:
                from utils import format_size
                text_str = f"{name[:18]}\n{format_size(size)}"
                self.create_text(
                    x + w / 2, y + h / 2,
                    text=text_str,
                    fill="#ffffff",
                    font=(Fonts.FAMILY, 9, "bold"),
                    justify="center",
                )

            self._rects.append((x + 1, y + 1, x + w - 1, y + h - 1, path, size, name, rect_id, color))
            return

        half = total / 2
        acc = 0
        split_idx = 1
        for i, item in enumerate(items):
            acc += item[1]
            if acc >= half or i == len(items) - 1:
                split_idx = max(1, i)
                break

        group1 = items[:split_idx]
        group2 = items[split_idx:]
        size1 = sum(s for _, s, _ in group1)
        size2 = sum(s for _, s, _ in group2)

        if w >= h:
            w1 = int(w * (size1 / total))
            w2 = w - w1
            self._partition(group1, x, y, w1, h, size1)
            self._partition(group2, x + w1, y, w2, h, size2)
        else:
            h1 = int(h * (size1 / total))
            h2 = h - h1
            self._partition(group1, x, y, w, h1, size1)
            self._partition(group2, x, y + h1, w, h2, size2)

    def _handle_motion(self, event):
        for x1, y1, x2, y2, path, size, name, rect_id, color in self._rects:
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                if self.on_hover:
                    from utils import format_size
                    self.on_hover(f"{name} ({format_size(size)})  ·  {path}")
                return
        if self.on_hover:
            self.on_hover("Hover over a block to inspect details")

    def _handle_click(self, event):
        for x1, y1, x2, y2, path, size, name, rect_id, color in self._rects:
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                if self.on_click:
                    self.on_click(path)
                return


class FilePreviewDialog(ctk.CTkToplevel):
    """Dialog showing file preview (image thumbnail or first text lines) + metadata."""

    IMAGE_EXTS = {"jpg", "jpeg", "png", "gif", "bmp", "webp", "ico"}
    TEXT_EXTS = {"txt", "py", "js", "json", "csv", "md", "html", "css", "log", "xml", "yaml", "ini", "bat", "sh"}

    def __init__(self, master, filepath, on_delete=None, on_open=None):
        super().__init__(master)
        self.filepath = filepath
        name = os.path.basename(filepath)
        self.title(f"Preview - {name}")
        self.geometry("560x440")
        self.resizable(False, False)
        self.configure(fg_color=Colors.BG_PRIMARY)
        self.transient(master)
        self.grab_set()

        # Center on parent
        self.update_idletasks()
        x = master.winfo_rootx() + (master.winfo_width() - 560) // 2
        y = master.winfo_rooty() + (master.winfo_height() - 440) // 2
        self.geometry(f"+{x}+{y}")

        # Top header
        header = ctk.CTkFrame(self, fg_color=Colors.BG_SECONDARY, height=48, corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text=f" 👁️  {name}",
            font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.SUBHEADING_SIZE, weight="bold"),
            text_color=Colors.TEXT_PRIMARY,
            anchor="w",
        ).pack(side="left", padx=Spacing.PAD_MD)

        # Body container
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=Spacing.PAD_MD, pady=Spacing.PAD_MD)

        ext = get_file_extension(filepath)

        if ext in self.IMAGE_EXTS and os.path.isfile(filepath):
            self._render_image_preview(body, filepath)
        elif ext in self.TEXT_EXTS and os.path.isfile(filepath):
            self._render_text_preview(body, filepath)
        else:
            self._render_info_preview(body, filepath)

        # Bottom Action Bar
        action_bar = ctk.CTkFrame(self, fg_color="transparent", height=44)
        action_bar.pack(fill="x", side="bottom", padx=Spacing.PAD_MD, pady=Spacing.PAD_SM)

        if on_open:
            ctk.CTkButton(
                action_bar,
                text="Open Location",
                width=110,
                height=32,
                corner_radius=Spacing.RADIUS_MD,
                fg_color=Colors.BG_TERTIARY,
                hover_color=Colors.BG_HOVER,
                text_color=Colors.TEXT_PRIMARY,
                command=lambda: (on_open(filepath), self.destroy()),
            ).pack(side="left")

        if on_delete:
            ctk.CTkButton(
                action_bar,
                text="Delete File",
                width=100,
                height=32,
                corner_radius=Spacing.RADIUS_MD,
                fg_color=Colors.RED_BG,
                hover_color=Colors.RED,
                text_color="#ffffff",
                font=ctk.CTkFont(family=Fonts.FAMILY, size=Fonts.BODY_SIZE, weight="bold"),
                command=lambda: (self.destroy(), on_delete(filepath)),
            ).pack(side="right", padx=(Spacing.PAD_SM, 0))

        ctk.CTkButton(
            action_bar,
            text="Close",
            width=80,
            height=32,
            corner_radius=Spacing.RADIUS_MD,
            fg_color=Colors.BG_TERTIARY,
            hover_color=Colors.BG_HOVER,
            text_color=Colors.TEXT_SECONDARY,
            command=self.destroy,
        ).pack(side="right")

    def _render_image_preview(self, parent, filepath):
        try:
            from PIL import Image
            img = Image.open(filepath)
            img.thumbnail((480, 240))
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)

            lbl = ctk.CTkLabel(parent, image=ctk_img, text="")
            lbl._img_ref = ctk_img
            self._preview_img = ctk_img
            lbl.pack(pady=Spacing.PAD_SM)
        except Exception as e:
            ctk.CTkLabel(parent, text=f"Could not load image preview: {e}", text_color=Colors.TEXT_MUTED).pack(pady=Spacing.PAD_MD)

        self._render_meta(parent, filepath)

    def _render_text_preview(self, parent, filepath):
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                lines = [f.readline() for _ in range(30)]
            content = "".join(lines).strip()
        except Exception as e:
            content = f"Error reading text: {e}"

        txt_box = ctk.CTkTextbox(
            parent,
            height=200,
            font=ctk.CTkFont(family=Fonts.MONO, size=Fonts.TINY_SIZE),
            fg_color=Colors.BG_SECONDARY,
            text_color=Colors.TEXT_PRIMARY,
        )
        txt_box.pack(fill="both", expand=True, pady=(0, Spacing.PAD_SM))
        txt_box.insert("1.0", content)
        txt_box.configure(state="disabled")

        self._render_meta(parent, filepath)

    def _render_info_preview(self, parent, filepath):
        ctk.CTkLabel(
            parent,
            text="📁" if os.path.isdir(filepath) else "📄",
            font=ctk.CTkFont(size=64),
            text_color=Colors.ACCENT,
        ).pack(pady=(Spacing.PAD_LG, Spacing.PAD_MD))

        self._render_meta(parent, filepath)

    def _render_meta(self, parent, filepath):
        meta_frame = ctk.CTkFrame(parent, fg_color=Colors.BG_SECONDARY, corner_radius=Spacing.RADIUS_SM)
        meta_frame.pack(fill="x", pady=Spacing.PAD_XS)

        try:
            sz = os.path.getsize(filepath) if os.path.exists(filepath) else 0
            mtime = format_timestamp(os.path.getmtime(filepath)) if os.path.exists(filepath) else "-"
        except Exception:
            sz, mtime = 0, "-"

        info = f"Path: {filepath}\nSize: {format_size(sz)}  ·  Modified: {mtime}"
        ctk.CTkLabel(
            meta_frame,
            text=info,
            font=ctk.CTkFont(family=Fonts.MONO, size=Fonts.TINY_SIZE),
            text_color=Colors.TEXT_MUTED,
            justify="left",
            anchor="w",
            wraplength=500,
        ).pack(padx=Spacing.PAD_SM, pady=Spacing.PAD_SM, anchor="w")
