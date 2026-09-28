"""カバー画像 (パッケージ画像) のトリミング編集ダイアログ.

- 取り込み元: 既存のカバー / ファイル / クリップボード (画像そのもの、またはエクスプローラーでコピーした画像ファイル)
- 範囲指定: ドラッグで移動、四隅で拡大縮小、ホイールで拡大縮小、範囲外ドラッグで新規指定
- 余白を許可すると、元画像の縦横比のまま 4:3 枠に収め、足りない部分を黒で埋められる (レターボックス)
- 保存: トリミング結果を <ROM名>.png として ROM と同じフォルダへ。
        元画像と範囲は .cover_originals/ に残し、後からやり直せるようにする
"""
from __future__ import annotations

import io
import json
import shutil
import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk
from typing import Callable, Optional

from . import config as C
from .capacity import COVER_SUFFIXES, cover_dims, find_cover, rom_stem

try:
    from PIL import Image, ImageEnhance, ImageFilter, ImageGrab, ImageOps, ImageTk
except ImportError:  # pragma: no cover - Pillow が無い環境
    Image = None  # type: ignore

ORIGINALS = ".cover_originals"
CANVAS_W, CANVAS_H = 640, 480
HANDLE = 10          # 四隅のつかみ判定 (画面px)
MIN_SIZE = 16        # 範囲の最小サイズ (画像px)
MAX_STORE_SCALE = 4  # 保存するトリミング画像は実機サイズの最大4倍まで


def originals_dir(rom: Path) -> Path:
    return rom.parent / ORIGINALS


def find_original(rom: Path) -> Optional[Path]:
    d = originals_dir(rom)
    stem = rom_stem(rom)
    for suf in COVER_SUFFIXES:
        p = d / (stem + suf)
        if p.exists():
            return p
    return None


def delete_cover_files(rom: Path, originals: bool = True) -> list[Path]:
    """ROM のカバー画像 (と任意で元画像・範囲情報) をすべて削除する."""
    removed = []
    while (c := find_cover(rom)) is not None:
        c.unlink()
        removed.append(c)
    if originals:
        d = originals_dir(rom)
        stem = rom_stem(rom)
        for suf in COVER_SUFFIXES + (".json",):
            p = d / (stem + suf)
            if p.exists():
                p.unlink()
                removed.append(p)
    return removed


def clipboard_image() -> Optional["Image.Image"]:
    data = ImageGrab.grabclipboard()
    if isinstance(data, Image.Image):
        return data
    if isinstance(data, list):  # エクスプローラーでファイルをコピーした場合
        for f in data:
            try:
                return Image.open(f)
            except (OSError, ValueError):
                continue
    return None


# ---- 余白 (画像の外側) の塗り方 --------------------------------------------
# カバーは JPEG に変換されて不透明な四角として描かれるため、本当の透過はできない。
# 代わりに Retro-Go メニューの背景色で塗れば、背景と同化して透過と同じ見た目になる。
# 背景色は Core/Src/retro-go/gui.c の gui_colors[] (配色) の bg_c。
#   _2C_(C): 24bit色 → RGB565、 _2CC(C): Zelda 版は赤成分を緑に置き換える (Mario 版は _2C_ と同じ)
_GUI_BG = [(0x000000, False)] * 6 + [(0x100000, True)] * 4 + [(0x000000, False)] * 2 + [
    (c, False) for c in (0x32435F, 0x2F1812, 0x002C2F, 0x5D353E, 0x171516, 0x3C1832, 0x2E1E11,
                         0x2C413C, 0x252839, 0x702020, 0x32435F, 0x704020, 0x525E76)]


def _rgb565(c: int, device: str, cc: bool) -> str:
    if cc and device == "zelda":
        v = ((c >> 0) & 0xF800) | ((c >> 13) & 0x7E0) | ((c >> 3) & 0x1F)
    else:
        v = ((c >> 8) & 0xF800) | ((c >> 5) & 0x7E0) | ((c >> 3) & 0x1F)
    r, g, b = (v >> 11) & 31, (v >> 5) & 63, v & 31
    return f"#{r * 255 // 31:02x}{g * 255 // 63:02x}{b * 255 // 31:02x}"


def fill_choices(device: str) -> list[tuple[str, str]]:
    """(表示名, 値)。値は '#rrggbb' または 'blur'."""
    out = [("黒（標準の配色では背景と同化）", "#000000"), ("白", "#ffffff"), ("ぼかし（画像を拡大してぼかす）", "blur")]
    seen = {"#000000", "#ffffff"}
    for i, (c, cc) in enumerate(_GUI_BG, 1):
        hexc = _rgb565(c, device, cc)
        if hexc not in seen:
            seen.add(hexc)
            out.append((f"Retro-Go 配色{i} の背景 {hexc}", hexc))
    return out


class CoverEditor(tk.Toplevel):
    """範囲 (box) は元画像の座標で持つ。余白を許可すると、画像の外側 (負の座標など) も範囲にできる."""

    def __init__(self, master: tk.Misc, rom: Path, settings: C.Settings,
                 on_saved: Callable[[], None], initial: Optional["Image.Image"] = None) -> None:
        super().__init__(master)
        self.rom = rom
        self.stem = rom_stem(rom)
        self.settings = settings
        self.quality = settings.jpg_quality
        self.on_saved = on_saved
        self.tw, self.th = cover_dims(rom.parent.name)
        self.ratio = self.tw / self.th
        self.src: Optional[Image.Image] = None
        self.src_is_new = False       # 貼り付け・ファイルから取り込んだ (元画像として保存が必要)
        self.src_path: Optional[Path] = None
        self.box = (0.0, 0.0, 0.0, 0.0)
        self.drag: Optional[dict] = None
        self._photo = self._prev_photo = None
        self._pending = False

        self.title(f"カバー編集 — {rom.name}")
        self.transient(master)
        self.resizable(False, False)
        self._build()
        self.bind("<Control-v>", lambda e: self.paste())
        self.bind("<Control-V>", lambda e: self.paste())
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Return>", lambda e: self.save())

        if initial is not None:
            self._set_source(initial, None, new=True)
        else:
            self._load_existing()
        self.grab_set()
        self.focus_set()

    # ------------------------------------------------------------------ UI
    def _build(self) -> None:
        top = ttk.Frame(self, padding=(10, 8))
        top.pack(fill=tk.X)
        ttk.Label(top, text=f"{self.rom.name}　→　実機では {self.tw}×{self.th} に引き伸ばして表示",
                  font=("Yu Gothic UI", 10, "bold")).pack(side=tk.LEFT)
        bar = ttk.Frame(self, padding=(10, 0))
        bar.pack(fill=tk.X)
        ttk.Button(bar, text="クリップボードから貼り付け (Ctrl+V)", command=self.paste).pack(side=tk.LEFT)
        ttk.Button(bar, text="ファイルを開く…", command=self.open_file).pack(side=tk.LEFT, padx=6)
        ttk.Separator(bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)
        ttk.Button(bar, text="全体を収める（黒帯）", command=self.fit_whole).pack(side=tk.LEFT)
        ttk.Button(bar, text="画面いっぱい（切り抜き）", command=self.fill_frame).pack(side=tk.LEFT, padx=6)

        bar2 = ttk.Frame(self, padding=(10, 4, 10, 0))
        bar2.pack(fill=tk.X)
        self.lock_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar2, text=f"縦横比を {self.tw}:{self.th} に固定（歪みなし）", variable=self.lock_var,
                        command=self._on_lock).pack(side=tk.LEFT)
        self.pad_var = tk.BooleanVar(value=self.settings.cover_pad)
        ttk.Checkbutton(bar2, text="画像の外側も範囲にできる", variable=self.pad_var,
                        command=self._on_pad).pack(side=tk.LEFT, padx=(16, 0))
        ttk.Label(bar2, text="　余白:").pack(side=tk.LEFT)
        self.fill_choices = fill_choices(self.settings.device)
        self.fill = self.settings.cover_pad_fill or "#000000"
        self.fill_var = tk.StringVar()
        self.fill_cb = ttk.Combobox(bar2, textvariable=self.fill_var, state="readonly", width=30)
        self.fill_cb.pack(side=tk.LEFT, padx=4)
        self.fill_cb.bind("<<ComboboxSelected>>", lambda e: self._on_fill_selected())
        self.fill_swatch = tk.Label(bar2, width=3, relief=tk.SOLID, borderwidth=1)
        self.fill_swatch.pack(side=tk.LEFT)
        self._sync_fill_widgets()

        body = ttk.Frame(self, padding=10)
        body.pack()
        self.canvas = tk.Canvas(body, width=CANVAS_W, height=CANVAS_H, background="#3a3a3a",
                                highlightthickness=0, cursor="crosshair")
        self.canvas.pack(side=tk.LEFT)
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._motion)
        self.canvas.bind("<ButtonRelease-1>", lambda e: setattr(self, "drag", None))
        self.canvas.bind("<MouseWheel>", self._wheel)
        self.canvas.bind("<Double-Button-1>", lambda e: self.fit_whole() if self.pad_var.get() else self.fill_frame())

        side = ttk.Frame(body, padding=(12, 0, 0, 0))
        side.pack(side=tk.LEFT, fill=tk.Y)
        ttk.Label(side, text="実機での見え方 (2倍表示)").pack(anchor=tk.W)
        self.prev = tk.Canvas(side, width=self.tw * 2, height=self.th * 2, background="#000000", highlightthickness=0)
        self.prev.pack(anchor=tk.W, pady=(4, 8))
        self.info = ttk.Label(side, justify=tk.LEFT, wraplength=self.tw * 2)
        self.info.pack(anchor=tk.W)
        ttk.Label(side, foreground="#57606a", justify=tk.LEFT, wraplength=self.tw * 2, text=(
            "操作:\n・枠の中をドラッグ: 移動\n・四隅をドラッグ: 拡大縮小\n・枠の外をドラッグ: 範囲を描き直す\n"
            "・ホイール: 拡大縮小\n・ダブルクリック: 全体を収める\n\n"
            "元画像は .cover_originals に残るので、後からトリミングし直せます。"
        )).pack(anchor=tk.W, pady=(12, 0))

        btns = ttk.Frame(self, padding=(10, 0, 10, 10))
        btns.pack(fill=tk.X)
        ttk.Button(btns, text="カバーを削除", command=self.delete).pack(side=tk.LEFT)
        ttk.Button(btns, text="キャンセル", command=self.destroy).pack(side=tk.RIGHT)
        ttk.Button(btns, text="保存", command=self.save).pack(side=tk.RIGHT, padx=6)

    # -------------------------------------------------------------- source
    def _load_existing(self) -> None:
        orig = find_original(self.rom)
        cur = find_cover(self.rom)
        path = orig or cur
        if path is None:
            self._render()
            self.info.configure(text="カバーがありません。\n画像をコピーして Ctrl+V で貼り付けるか、\n「ファイルを開く…」で取り込んでください。")
            return
        try:
            img = Image.open(path)
            img.load()
        except (OSError, ValueError) as e:
            messagebox.showerror(self.title(), f"画像を読み込めません: {e}", parent=self)
            return
        meta = None
        if orig:
            try:
                meta = json.loads(orig.with_suffix(".json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                meta = None
        if meta and "pad" in meta:
            self.pad_var.set(bool(meta["pad"]))
        if meta and meta.get("fill"):
            self.fill = meta["fill"]
            self._sync_fill_widgets()
        self._set_source(img, path, new=False)
        if meta:
            try:
                self.box = self._clamp_box(tuple(float(v) for v in meta["box"]))
                self._render()
            except (KeyError, TypeError, ValueError):
                pass

    def _set_source(self, img: "Image.Image", path: Optional[Path], new: bool) -> None:
        self.src = img.convert("RGB")
        self.src_path = path
        self.src_is_new = new
        iw, ih = self.src.size
        # 画面の縮尺は「画像全体を収めた 4:3 枠」が入る大きさに固定する (余白の切り替えで表示が動かないように)
        fx0, fy0, fx1, fy1 = self._fit_box()
        self.scale = min(CANVAS_W / (fx1 - fx0), CANVAS_H / (fy1 - fy0)) * 0.96
        self.ox = CANVAS_W / 2 - iw / 2 * self.scale
        self.oy = CANVAS_H / 2 - ih / 2 * self.scale
        shown = self.src.resize((max(1, round(iw * self.scale)), max(1, round(ih * self.scale))),
                                Image.Resampling.LANCZOS)
        self._photo = ImageTk.PhotoImage(shown)
        if path is not None and path.parent == self.rom.parent:
            self.box = (0.0, 0.0, float(iw), float(ih))  # 既存のカバー (トリミング済み) はそのまま全体
        elif self.pad_var.get():
            self.box = self._fit_box()
        else:
            self.box = self._fill_box()
        self._render()

    def paste(self) -> None:
        img = clipboard_image()
        if img is None:
            messagebox.showinfo(self.title(), "クリップボードに画像がありません。\n"
                                              "ブラウザ等で画像をコピーするか、エクスプローラーで画像ファイルをコピーしてください。",
                                parent=self)
            return
        self._set_source(img, None, new=True)

    def open_file(self) -> None:
        f = filedialog.askopenfilename(parent=self, title="カバー画像を開く",
                                       filetypes=[("画像", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"), ("すべて", "*.*")])
        if not f:
            return
        try:
            img = Image.open(f)
            img.load()
        except (OSError, ValueError) as e:
            messagebox.showerror(self.title(), f"画像を読み込めません: {e}", parent=self)
            return
        self._set_source(img, None, new=True)

    # ------------------------------------------------------------- bounds
    def _fit_box(self) -> tuple:
        """画像全体が収まる最小の 4:3 枠 (画像の中央に配置)."""
        iw, ih = self.src.size
        w = max(iw, ih * self.ratio)
        h = w / self.ratio
        return ((iw - w) / 2, (ih - h) / 2, (iw + w) / 2, (ih + h) / 2)

    def _fill_box(self) -> tuple:
        """画像の内側に収まる最大の 4:3 枠."""
        iw, ih = self.src.size
        w = min(iw, ih * self.ratio)
        h = w / self.ratio
        return ((iw - w) / 2, (ih - h) / 2, (iw + w) / 2, (ih + h) / 2)

    def _bounds(self) -> tuple:
        """範囲を動かせる領域。余白ありなら全体を収めた 4:3 枠、なしなら画像そのもの."""
        if self.pad_var.get():
            return self._fit_box()
        iw, ih = self.src.size
        return (0.0, 0.0, float(iw), float(ih))

    def _clamp_box(self, box: tuple) -> tuple:
        bx0, by0, bx1, by1 = self._bounds()
        x0, y0, x1, y1 = box
        x0, x1 = sorted((max(bx0, min(bx1, x0)), max(bx0, min(bx1, x1))))
        y0, y1 = sorted((max(by0, min(by1, y0)), max(by0, min(by1, y1))))
        return (x0, y0, x1, y1)

    def fit_whole(self) -> None:
        if not self.src:
            return
        if not self.pad_var.get():
            self.pad_var.set(True)
            self._save_pad_pref()
        self.lock_var.set(True)
        self.box = self._fit_box()
        self._render()

    def fill_frame(self) -> None:
        if not self.src:
            return
        self.lock_var.set(True)
        self.box = self._fill_box()
        self._render()

    # ---------------------------------------------------------------- fill
    CUSTOM = "色を選ぶ…"

    def _sync_fill_widgets(self) -> None:
        values = [label for label, _ in self.fill_choices]
        label = next((lb for lb, v in self.fill_choices if v == self.fill), None)
        if label is None:
            label = f"指定色 {self.fill}"
            values.append(label)
        self.fill_cb.configure(values=values + [self.CUSTOM])
        self.fill_var.set(label)
        if self.fill == "blur":
            self.fill_swatch.configure(background="#808080", text="≈")
        else:
            self.fill_swatch.configure(background=self.fill, text="")

    def _on_fill_selected(self) -> None:
        label = self.fill_var.get()
        if label == self.CUSTOM:
            init = self.fill if self.fill.startswith("#") else "#000000"
            _, hexc = colorchooser.askcolor(color=init, parent=self, title="余白の色")
            if hexc:
                self.fill = hexc.lower()
        elif label.startswith("指定色 "):
            self.fill = label.split(" ", 1)[1]
        else:
            self.fill = dict(self.fill_choices).get(label, self.fill)
        self.settings.cover_pad_fill = self.fill
        self.settings.save()
        self._sync_fill_widgets()
        self._render()

    def _pad_base(self, w: int, h: int) -> "Image.Image":
        """余白部分の下地."""
        if self.fill == "blur":
            base = ImageOps.fit(self.src, (w, h), Image.Resampling.BILINEAR)
            base = base.filter(ImageFilter.GaussianBlur(radius=max(w, h) / 25))
            return ImageEnhance.Brightness(base).enhance(0.7)
        return Image.new("RGB", (w, h), self.fill)

    def _save_pad_pref(self) -> None:
        self.settings.cover_pad = bool(self.pad_var.get())
        self.settings.save()

    def _on_pad(self) -> None:
        self._save_pad_pref()
        if self.src:
            x0, y0, x1, y1 = self.box
            self._resize_about((x0 + x1) / 2, (y0 + y1) / 2, x1 - x0)
        self._render()

    def _on_lock(self) -> None:
        if self.src and self.lock_var.get():
            x0, y0, x1, y1 = self.box
            self._resize_about((x0 + x1) / 2, (y0 + y1) / 2, x1 - x0)
        self._render()

    def _resize_about(self, cx: float, cy: float, w: float) -> None:
        bx0, by0, bx1, by1 = self._bounds()
        bw, bh = bx1 - bx0, by1 - by0
        x0, y0, x1, y1 = self.box
        h = w / self.ratio if self.lock_var.get() else (y1 - y0) * w / max(x1 - x0, 1)
        k = min(1.0, bw / w, bh / h)  # 動かせる領域に収まるよう縮める
        w, h = max(MIN_SIZE, w * k), max(MIN_SIZE / self.ratio, h * k)
        nx = min(max(bx0, cx - w / 2), bx1 - w)
        ny = min(max(by0, cy - h / 2), by1 - h)
        self.box = (nx, ny, nx + w, ny + h)

    # --------------------------------------------------------------- mouse
    def _to_img(self, x: float, y: float) -> tuple[float, float]:
        return (x - self.ox) / self.scale, (y - self.oy) / self.scale

    def _to_canvas(self, x: float, y: float) -> tuple[float, float]:
        return x * self.scale + self.ox, y * self.scale + self.oy

    def _press(self, e) -> None:
        if not self.src:
            return
        x0, y0, x1, y1 = self.box
        corners = {(0, 0): (x1, y1), (1, 0): (x0, y1), (0, 1): (x1, y0), (1, 1): (x0, y0)}
        for (cx, cy), anchor in corners.items():
            px, py = self._to_canvas(x1 if cx else x0, y1 if cy else y0)
            if abs(e.x - px) <= HANDLE and abs(e.y - py) <= HANDLE:
                self.drag = {"mode": "resize", "anchor": anchor}
                return
        ix, iy = self._to_img(e.x, e.y)
        if x0 <= ix <= x1 and y0 <= iy <= y1:
            self.drag = {"mode": "move", "last": (ix, iy)}
        else:
            bx0, by0, bx1, by1 = self._bounds()
            self.drag = {"mode": "resize", "anchor": (max(bx0, min(bx1, ix)), max(by0, min(by1, iy)))}

    def _motion(self, e) -> None:
        if not self.drag or not self.src:
            return
        bx0, by0, bx1, by1 = self._bounds()
        ix, iy = self._to_img(e.x, e.y)
        if self.drag["mode"] == "move":
            lx, ly = self.drag["last"]
            x0, y0, x1, y1 = self.box
            w, h = x1 - x0, y1 - y0
            nx = min(max(bx0, x0 + ix - lx), bx1 - w)
            ny = min(max(by0, y0 + iy - ly), by1 - h)
            self.box = (nx, ny, nx + w, ny + h)
            self.drag["last"] = (ix, iy)
        else:
            ax, ay = self.drag["anchor"]
            sx = 1 if ix >= ax else -1
            sy = 1 if iy >= ay else -1
            w, h = abs(ix - ax), abs(iy - ay)
            room_w = (bx1 - ax) if sx > 0 else (ax - bx0)
            room_h = (by1 - ay) if sy > 0 else (ay - by0)
            if self.lock_var.get():
                w = max(w, h * self.ratio)
                w = min(w, room_w, room_h * self.ratio)
                h = w / self.ratio
            else:
                w, h = min(w, room_w), min(h, room_h)
            if w < MIN_SIZE or h < MIN_SIZE / self.ratio:
                return
            self.box = self._clamp_box((ax, ay, ax + sx * w, ay + sy * h))
        self._render()

    def _wheel(self, e) -> None:
        if not self.src:
            return
        x0, y0, x1, y1 = self.box
        self._resize_about((x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) * (0.9 if e.delta > 0 else 1.1))
        self._render()

    # ------------------------------------------------------------- render
    def _render(self) -> None:
        c = self.canvas
        c.delete("all")
        if not self.src:
            c.create_text(CANVAS_W / 2, CANVAS_H / 2, fill="#8c959f", font=("Yu Gothic UI", 12),
                          text="画像をコピーして Ctrl+V で貼り付け\nまたは「ファイルを開く…」", justify=tk.CENTER)
            return
        if self.pad_var.get():  # 余白になりうる領域を、実際の余白の塗りで示す
            fx0, fy0 = self._to_canvas(*self._fit_box()[:2])
            fx1, fy1 = self._to_canvas(*self._fit_box()[2:])
            if self.fill == "blur":
                size = (max(1, round(fx1 - fx0)), max(1, round(fy1 - fy0)))
                key = (id(self.src), size)
                if getattr(self, "_blur_key", None) != key:
                    self._blur_key = key
                    self._blur_photo = ImageTk.PhotoImage(self._pad_base(*size))
                c.create_image(fx0, fy0, image=self._blur_photo, anchor=tk.NW)
            else:
                c.create_rectangle(fx0, fy0, fx1, fy1, fill=self.fill, width=0)
        c.create_image(self.ox, self.oy, image=self._photo, anchor=tk.NW)
        iw, ih = self.src.size
        # 元画像の範囲 (背景が黒い画像でも黒い余白と区別できるように)
        c.create_rectangle(*self._to_canvas(0, 0), *self._to_canvas(iw, ih), outline="#8c959f", dash=(4, 3))
        x0, y0 = self._to_canvas(*self.box[:2])
        x1, y1 = self._to_canvas(*self.box[2:])
        for rect in ((0, 0, CANVAS_W, y0), (0, y1, CANVAS_W, CANVAS_H), (0, y0, x0, y1), (x1, y0, CANVAS_W, y1)):
            c.create_rectangle(*rect, fill="#000000", stipple="gray50", width=0)
        c.create_rectangle(x0, y0, x1, y1, outline="#ffd33d", width=2)
        for px, py in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
            c.create_rectangle(px - 5, py - 5, px + 5, py + 5, fill="#ffd33d", outline="#000000")
        if not self._pending:
            self._pending = True
            self.after(60, self._update_preview)

    def _cropped(self) -> "Image.Image":
        """範囲を切り出す。画像の外側は余白の設定 (単色 / ぼかし) で埋める."""
        x0, y0, x1, y1 = (round(v) for v in self.box)
        w, h = max(1, x1 - x0), max(1, y1 - y0)
        iw, ih = self.src.size
        if x0 >= 0 and y0 >= 0 and x1 <= iw and y1 <= ih:
            return self.src.crop((x0, y0, x0 + w, y0 + h))
        out = self._pad_base(w, h)
        sx0, sy0 = max(0, x0), max(0, y0)
        sx1, sy1 = min(iw, x0 + w), min(ih, y0 + h)
        if sx1 > sx0 and sy1 > sy0:
            out.paste(self.src.crop((sx0, sy0, sx1, sy1)), (sx0 - x0, sy0 - y0))
        return out

    def _update_preview(self) -> None:
        self._pending = False
        if not self.src:
            return
        # parse_roms.py の write_covart と同じ変換を再現して見た目とサイズを出す
        small = self._cropped().resize((self.tw, self.th), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        small.save(buf, format="JPEG", optimize=True, quality=self.quality)
        size = buf.tell()
        buf.seek(0)
        jpg = Image.open(buf)
        self._prev_photo = ImageTk.PhotoImage(jpg.resize((self.tw * 2, self.th * 2), Image.Resampling.NEAREST))
        self.prev.delete("all")
        self.prev.create_image(0, 0, image=self._prev_photo, anchor=tk.NW)
        x0, y0, x1, y1 = self.box
        w, h = x1 - x0, y1 - y0
        iw, ih = self.src.size
        distort = abs((w / max(h, 1)) - self.ratio) / self.ratio
        notes = []
        if distort > 0.02:
            notes.append(f"⚠ 縦横比が違うため {distort * 100:.0f}% 歪みます")
        if x0 < -0.5 or y0 < -0.5 or x1 > iw + 0.5 or y1 > ih + 0.5:
            fill_name = next((lb for lb, v in self.fill_choices if v == self.fill), self.fill).split("（")[0]
            notes.append(f"余白: {fill_name}")
        self.info.configure(text=f"範囲: {w:.0f}×{h:.0f} px（元 {iw}×{ih}）\n"
                                 f"書き込みサイズ: 約 {size / 1024:.1f} KB（JPEG品質 {self.quality}）"
                                 + "".join("\n" + n for n in notes))

    # --------------------------------------------------------------- save
    def save(self) -> None:
        if not self.src:
            messagebox.showinfo(self.title(), "画像がありません。", parent=self)
            return
        od = originals_dir(self.rom)
        od.mkdir(exist_ok=True)
        # 元画像を保存 (初回、または新しく取り込んだとき)
        if self.src_is_new or find_original(self.rom) is None:
            for suf in COVER_SUFFIXES:
                (od / (self.stem + suf)).unlink(missing_ok=True)
            if self.src_path is not None and self.src_path.suffix.lower() in COVER_SUFFIXES and not self.src_is_new:
                shutil.copy2(self.src_path, od / (self.stem + self.src_path.suffix.lower()))
            else:
                self.src.save(od / (self.stem + ".png"))
        (od / (self.stem + ".json")).write_text(json.dumps({
            "box": [round(v, 2) for v in self.box], "target": [self.tw, self.th], "pad": bool(self.pad_var.get()),
            "fill": self.fill,
        }), encoding="utf-8")

        out = self._cropped()
        limit = (self.tw * MAX_STORE_SCALE, self.th * MAX_STORE_SCALE)
        if out.width > limit[0] or out.height > limit[1]:
            out.thumbnail(limit, Image.Resampling.LANCZOS)
        delete_cover_files(self.rom, originals=False)
        out.save(self.rom.parent / (self.stem + ".png"))
        self.on_saved()
        self.destroy()

    def delete(self) -> None:
        if messagebox.askyesno(self.title(), f"{self.rom.name} のカバー画像（元画像を含む）を削除しますか？", parent=self):
            delete_cover_files(self.rom, originals=True)
            self.on_saved()
            self.destroy()


def available() -> bool:
    return Image is not None


def open_editor(master: tk.Misc, rom: Path, settings: C.Settings, on_saved: Callable[[], None],
                paste: bool = False) -> None:
    if not available():
        messagebox.showerror(C.APP_NAME, "カバー編集には Pillow が必要です。\n"
                                         "コマンドプロンプトで  python -m pip install pillow  を実行してください。")
        return
    initial = None
    if paste:
        initial = clipboard_image()
        if initial is None:
            messagebox.showinfo(C.APP_NAME, "クリップボードに画像がありません。")
            return
    CoverEditor(master, rom, settings, on_saved, initial)
