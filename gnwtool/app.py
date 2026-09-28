"""Tkinter GUI."""
from __future__ import annotations

import os
import queue
import shlex
import shutil
import subprocess
import threading
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Callable, Optional

from . import config as C
from . import cover_editor as CE
from . import package as P
from . import toolchain as T
from .capacity import (ALL_COVER_SUFFIXES, Estimate, Estimator, cover_dims, find_cover, parse_build_usage,
                       parse_overflow, rom_stem)

Step = tuple[str, Callable]  # (説明, fn(log, proc_hook))


class Cancelled(Exception):
    pass


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(C.APP_NAME)
        self.geometry("980x760")
        self.minsize(820, 620)
        self.settings = C.Settings.load()
        self.log_q: "queue.Queue[str]" = queue.Queue()
        self.worker: Optional[threading.Thread] = None
        self.proc: Optional[subprocess.Popen] = None
        self.cancel_flag = threading.Event()
        self.busy_widgets: list[tk.Widget] = []
        self._captured: list[str] = []

        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Ok.TLabel", foreground="#1a7f37")
        style.configure("Ng.TLabel", foreground="#cf222e")
        style.configure("H.TLabel", font=("Yu Gothic UI", 11, "bold"))
        style.configure("Big.TButton", font=("Yu Gothic UI", 11, "bold"), padding=8)

        self._build_device_bar()
        paned = ttk.PanedWindow(self, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.nb = ttk.Notebook(paned)
        paned.add(self.nb, weight=3)
        paned.add(self._build_log(paned), weight=2)

        self._tab_env()
        self._tab_backup()
        self._tab_config()
        self._tab_roms()
        self._tab_flash()

        self._apply_device()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._pump_log)
        self.after(200, self.refresh_status)

    # --------------------------------------------------------------- device
    def _build_device_bar(self) -> None:
        bar = ttk.Frame(self, padding=(10, 8, 10, 6))
        bar.pack(fill=tk.X)
        ttk.Label(bar, text="改造する本体:", style="H.TLabel").pack(side=tk.LEFT)
        self.device_var = tk.StringVar(value=self.settings.device)
        for key, dev in C.DEVICES.items():
            rb = ttk.Radiobutton(bar, text=f"{dev['name']} 版", value=key, variable=self.device_var,
                                 command=self._on_device_change)
            rb.pack(side=tk.LEFT, padx=8)
            self.busy_widgets.append(rb)
        self.theme_label = tk.Label(bar, font=("Yu Gothic UI", 10, "bold"))
        self.theme_label.pack(side=tk.RIGHT)

    def _on_device_change(self) -> None:
        self._collect_settings()          # 切り替え前の機種の値を保存
        self.settings.device = self.device_var.get()
        self.settings.save()
        self._apply_device()

    def _apply_device(self) -> None:
        s = self.settings
        dev = s.dev
        name, color = dev["theme"]
        self.theme_label.configure(text=f"Retro-Go のメニューテーマ: {name}", foreground=color)
        self.title(f"{C.APP_NAME} — {dev['name']} 版")
        self.backup_var.set(s.backup_dir)
        int_name, ext_name = C.backup_names(s.device)
        self.backup_desc.configure(text=(
            f"gnwmanager / game-and-watch-backup で吸い出した{dev['name']}版のバックアップを指定してください。\n"
            "このファイルはパッチ作成と「純正に戻す」に必須です。紛失すると復元できないため、別の場所にも必ず保管してください。"))
        self.backup_files.configure(text=(
            f"必要なファイル: {int_name} (128KB) / {ext_name} ({dev['ext_size'] // (1024 * 1024)}MB)"))
        # 外部フラッシュ容量の選択肢を作り直す
        for w in self.flash_box.winfo_children():
            w.destroy()
        sizes = C.flash_sizes(s.device)
        self.flash_var.set(s.flash_mb if s.flash_mb in sizes else dev["stock_mb"])
        for mb, label in sizes.items():
            ttk.Radiobutton(self.flash_box, text=label, value=mb, variable=self.flash_var,
                            command=self._update_preview).pack(side=tk.LEFT, padx=6)
        self.zelda_opts.pack_forget()
        self.mario_opts.pack_forget()
        (self.zelda_opts if s.device == "zelda" else self.mario_opts).pack(fill=tk.X)
        self.boot_hint.configure(text=(
            f"完了後: 通常起動で純正の{dev['name']}、「十字キー左 + GAME」ボタン同時押しで Retro-Go が起動します。"))
        self.controls_label.configure(text=dev["controls"])
        self._update_preview()
        self.verify_backup()
        self.refresh_builds()

    # ------------------------------------------------------------------ log
    def _build_log(self, parent) -> ttk.Frame:
        f = ttk.Frame(parent)
        bar = ttk.Frame(f)
        bar.pack(fill=tk.X)
        self.status_var = tk.StringVar(value="待機中")
        ttk.Label(bar, textvariable=self.status_var).pack(side=tk.LEFT)
        self.progress = ttk.Progressbar(bar, mode="determinate", length=160)
        self.progress.pack(side=tk.LEFT, padx=8)
        self.cancel_btn = ttk.Button(bar, text="中止", command=self.cancel, state=tk.DISABLED)
        self.cancel_btn.pack(side=tk.RIGHT)
        ttk.Button(bar, text="ログを消去", command=lambda: self.log_text.delete("1.0", tk.END)).pack(side=tk.RIGHT, padx=4)
        self.log_text = ScrolledText(f, height=12, font=("Consolas", 9), wrap=tk.CHAR)
        self.log_text.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.log_text.tag_configure("cmd", foreground="#0550ae")
        self.log_text.tag_configure("err", foreground="#cf222e")
        self.log_text.tag_configure("ok", foreground="#1a7f37")
        return f

    def log(self, line: str) -> None:
        self._captured.append(line)
        self.log_q.put(line)

    def _pump_log(self) -> None:
        lines = []
        try:
            while len(lines) < 500:
                lines.append(self.log_q.get_nowait())
        except queue.Empty:
            pass
        for line in lines:
            tag = ""
            low = line.lower()
            if line.startswith("$ ") or line.startswith("▶"):
                tag = "cmd"
            elif "error" in low or "失敗" in line or "エラー" in line:
                tag = "err"
            elif line.startswith("✔"):
                tag = "ok"
            self.log_text.insert(tk.END, line + "\n", tag)
        if lines:
            self.log_text.see(tk.END)
        self.after(100, self._pump_log)

    # --------------------------------------------------------------- worker
    def run_steps(self, title: str, steps: list[Step], on_done: Optional[Callable] = None) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showwarning(C.APP_NAME, "別の処理を実行中です。")
            return
        self.settings.save()
        self.cancel_flag.clear()
        self._captured = []
        self._set_busy(True, title)

        def hook(p):
            self.proc = p
            if self.cancel_flag.is_set():
                self._kill_proc()

        def work():
            ok = False
            try:
                for i, (desc, fn) in enumerate(steps, 1):
                    if self.cancel_flag.is_set():
                        raise Cancelled()
                    self.log(f"▶ [{i}/{len(steps)}] {desc}")
                    self.status_var.set(f"{title}: {desc}")
                    fn(self.log, hook)
                    if self.cancel_flag.is_set():
                        raise Cancelled()
                ok = True
                self.log(f"✔ {title} が完了しました")
            except Cancelled:
                self.log("中止しました")
            except Exception as e:  # noqa: BLE001
                self.log(f"エラー: {e}")
            finally:
                self.proc = None
                self.after(0, lambda: self._finish(title, ok, on_done))

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def _finish(self, title: str, ok: bool, on_done) -> None:
        self._set_busy(False, f"{title}: {'完了' if ok else '失敗/中止'}")
        self._apply_build_result(self._captured)
        self.refresh_status()
        if on_done:
            on_done(ok)
        if not ok and not self.cancel_flag.is_set():
            messagebox.showerror(C.APP_NAME, f"{title} に失敗しました。ログを確認してください。")

    def _set_busy(self, busy: bool, text: str) -> None:
        self.status_var.set(text)
        for w in self.busy_widgets:
            try:
                w.configure(state=tk.DISABLED if busy else tk.NORMAL)
            except tk.TclError:
                pass
        self.cancel_btn.configure(state=tk.NORMAL if busy else tk.DISABLED)
        if not busy:
            self.after(0, self._update_write_buttons)
        if busy:
            self.progress.configure(mode="indeterminate")
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.configure(mode="determinate", value=0)

    def cancel(self) -> None:
        self.cancel_flag.set()
        self._kill_proc()

    def _kill_proc(self) -> None:
        p = self.proc
        if p and p.poll() is None:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True,
                           creationflags=T.NO_WINDOW)

    def _on_close(self) -> None:
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno(C.APP_NAME, "処理を実行中です。中止して終了しますか？\n（書き込み中の中断は危険です）"):
                return
            self.cancel()
        self._collect_settings()
        self.settings.save()
        self.destroy()

    def _btn(self, parent, text, cmd, style=None, **pack) -> ttk.Button:
        b = ttk.Button(parent, text=text, command=cmd, style=style or "TButton")
        b.pack(**pack)
        self.busy_widgets.append(b)
        return b

    # ------------------------------------------------------- shell helpers
    @staticmethod
    def sh(cmd: str, cwd: Path) -> Callable:
        def fn(log, hook):
            T.run_cmd([str(T.bash_exe()), "-c", cmd], log, cwd=cwd, proc_hook=hook)
        return fn

    def _jobs(self) -> int:
        return max(1, (os.cpu_count() or 4))

    # ================================================================ TAB 1
    def _tab_env(self) -> None:
        f = ttk.Frame(self.nb, padding=12)
        self.nb.add(f, text=" ① 環境セットアップ ")
        ttk.Label(f, text="ビルド・書き込みに必要なツールを確認/自動導入します", style="H.TLabel").pack(anchor=tk.W)
        ttk.Label(f, text="ツールはこのフォルダの tools\\ 以下に導入され、PCの環境は汚しません。"
                          "Git for Windows のみ事前インストールが必要です。").pack(anchor=tk.W, pady=(2, 10))

        grid = ttk.Frame(f)
        grid.pack(fill=tk.X)
        self.env_rows: dict[str, tuple[ttk.Label, ttk.Label]] = {}
        names = [
            ("git", "Git for Windows (bash)"),
            ("repos", "ソース (patch / retro-go)"),
            ("venv", "Python環境 + gnwmanager"),
            ("make", "GNU make"),
            ("gcc", "ARM GCC ツールチェーン"),
            ("openocd", "OpenOCD (ST-Link書き込み)"),
        ]
        for r, (key, label) in enumerate(names):
            ttk.Label(grid, text=label, width=28).grid(row=r, column=0, sticky=tk.W, pady=2)
            mark = ttk.Label(grid, text="…", width=3)
            mark.grid(row=r, column=1)
            detail = ttk.Label(grid, text="", foreground="#57606a")
            detail.grid(row=r, column=2, sticky=tk.W)
            self.env_rows[key] = (mark, detail)

        bar = ttk.Frame(f)
        bar.pack(fill=tk.X, pady=12)
        self._btn(bar, "すべて自動セットアップ", self.do_setup, style="Big.TButton", side=tk.LEFT)
        self._btn(bar, "再チェック", self.refresh_status, side=tk.LEFT, padx=6)
        self._btn(bar, "ソースを最新に更新", self.do_update, side=tk.LEFT)
        ttk.Button(bar, text="Git for Windows 入手先", command=lambda: webbrowser.open("https://git-scm.com/download/win")).pack(side=tk.RIGHT)

        note = ttk.LabelFrame(f, text="ST-Link ドライバ", padding=8)
        note.pack(fill=tk.X)
        ttk.Label(note, justify=tk.LEFT, text=(
            "ST-Link を初めて使う場合は ST 公式の USB ドライバ (STSW-LINK009) をインストールしてください。\n"
            "配線は GND / SWDIO / SWCLK のみ。ST-Link の 3.3V と本体の VDD は絶対に接続しないでください。"
        )).pack(anchor=tk.W)
        ttk.Button(note, text="STSW-LINK009 のページを開く",
                   command=lambda: webbrowser.open("https://www.st.com/en/development-tools/stsw-link009.html")).pack(anchor=tk.W, pady=(6, 0))

    def refresh_status(self) -> None:
        def work():
            st = T.status()
            self.after(0, lambda: self._show_status(st))
        threading.Thread(target=work, daemon=True).start()

    def _show_status(self, st) -> None:
        for key, (ok, detail) in st.items():
            mark, lab = self.env_rows[key]
            mark.configure(text="✔" if ok else "✖", style="Ok.TLabel" if ok else "Ng.TLabel")
            lab.configure(text=detail)
        self.env_ready = all(ok for ok, _ in st.values())
        self.refresh_roms()

    def do_setup(self) -> None:
        if not T.find_git_root():
            messagebox.showerror(C.APP_NAME, "Git for Windows が見つかりません。インストール後に再実行してください。")
            return
        self.run_steps("環境セットアップ", [
            ("ソースコードを取得 (初回は数分かかります)", T.setup_repos),
            ("Python環境を構築", T.setup_venv),
            ("GNU make を導入", T.setup_make),
            ("ARM GCC を導入", T.setup_gcc),
            ("OpenOCD を導入", T.setup_openocd),
        ])

    def do_update(self) -> None:
        self.run_steps("ソース更新", [("git pull", T.update_repos), ("Python依存関係を更新", T.setup_venv)])

    # ================================================================ TAB 2
    def _tab_backup(self) -> None:
        f = ttk.Frame(self.nb, padding=12)
        self.nb.add(f, text=" ② バックアップ ")
        ttk.Label(f, text="純正ファームウェアのバックアップ", style="H.TLabel").pack(anchor=tk.W)
        self.backup_desc = ttk.Label(f, justify=tk.LEFT)
        self.backup_desc.pack(anchor=tk.W, pady=(2, 10))
        row = ttk.Frame(f)
        row.pack(fill=tk.X)
        ttk.Label(row, text="フォルダ:").pack(side=tk.LEFT)
        self.backup_var = tk.StringVar(value=self.settings.backup_dir)
        ttk.Entry(row, textvariable=self.backup_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ttk.Button(row, text="参照…", command=self._pick_backup).pack(side=tk.LEFT)
        ttk.Button(row, text="検証", command=self.verify_backup).pack(side=tk.LEFT, padx=6)
        self.backup_result = ttk.Frame(f)
        self.backup_result.pack(fill=tk.X, pady=10)
        self.backup_files = ttk.Label(f, foreground="#57606a")
        self.backup_files.pack(anchor=tk.W)

    def _pick_backup(self) -> None:
        d = filedialog.askdirectory(initialdir=self.backup_var.get() or str(C.ROOT))
        if d:
            self.backup_var.set(d)
            self.verify_backup()

    def verify_backup(self) -> bool:
        for w in self.backup_result.winfo_children():
            w.destroy()
        results = T.verify_backups(Path(self.backup_var.get()), self.settings.device)
        for name, ok, msg in results:
            ttk.Label(self.backup_result, text=f"{'✔' if ok else '✖'} {name}: {msg}",
                      style="Ok.TLabel" if ok else "Ng.TLabel").pack(anchor=tk.W)
        return all(ok for _, ok, _ in results)

    # ================================================================ TAB 3
    def _tab_config(self) -> None:
        s = self.settings
        f = ttk.Frame(self.nb, padding=12)
        self.nb.add(f, text=" ③ 構成 ")

        self.flash_box = ttk.LabelFrame(f, text="外部フラッシュ容量", padding=8)
        self.flash_box.pack(fill=tk.X)
        self.flash_var = tk.IntVar(value=s.flash_mb)

        box = ttk.LabelFrame(f, text="純正ファーム側 (game-and-watch-patch)", padding=8)
        box.pack(fill=tk.X, pady=8)
        self.opt_vars: dict[str, tk.Variable] = {}

        def chk(parent, key, text):
            v = tk.BooleanVar(value=getattr(s, key))
            self.opt_vars[key] = v
            ttk.Checkbutton(parent, text=text, variable=v, command=self._update_preview).pack(anchor=tk.W)

        self.zelda_opts = ttk.Frame(box)
        chk(self.zelda_opts, "no_second_beep", "時計の2回目のビープ音を消す (--no-second-beep)")
        chk(self.zelda_opts, "no_hour_tune", "時報メロディを消す (--no-hour-tune)")
        self.lite_note = ttk.Label(self.zelda_opts, foreground="#9a6700",
                                   text="※ 4MB構成では空き容量確保のため「夢をみる島」とスリープ画像が削除されます")
        self.lite_note.pack(anchor=tk.W)

        self.mario_opts = ttk.Frame(box)
        self.keep_extras_cb = ttk.Checkbutton(
            self.mario_opts, text="スリープ画像・マリオの歌の隠し要素を残す（外部フラッシュ先頭1MBを純正用に使用）",
            variable=tk.BooleanVar(), command=self._update_preview)
        self.opt_vars["mario_keep_extras"] = tk.BooleanVar(value=s.mario_keep_extras)
        self.keep_extras_cb.configure(variable=self.opt_vars["mario_keep_extras"])
        self.keep_extras_cb.pack(anchor=tk.W)
        self.mario_note = ttk.Label(self.mario_opts, foreground="#9a6700", justify=tk.LEFT)
        self.mario_note.pack(anchor=tk.W)

        box = ttk.LabelFrame(f, text="エミュレータ側 (Retro-Go)", padding=8)
        box.pack(fill=tk.X)
        row = ttk.Frame(box)
        row.pack(fill=tk.X)
        ttk.Label(row, text="メニュー言語/文字コード:").pack(side=tk.LEFT)
        self.cp_var = tk.StringVar(value=C.CODEPAGES.get(s.codepage, s.codepage))
        cb = ttk.Combobox(row, textvariable=self.cp_var, values=list(C.CODEPAGES.values()), state="readonly", width=22)
        cb.pack(side=tk.LEFT, padx=6)
        cb.bind("<<ComboboxSelected>>", lambda e: self._update_preview())
        chk(box, "state_saving", "ステートセーブを有効にする")
        row = ttk.Frame(box)
        row.pack(fill=tk.X)
        v = tk.BooleanVar(value=s.coverflow)
        self.opt_vars["coverflow"] = v
        ttk.Checkbutton(row, text="カバーアート表示 (COVERFLOW、ROMと同名の画像を 128×96 のJPEGに変換して格納)",
                        variable=v, command=self._update_preview).pack(side=tk.LEFT)
        ttk.Label(row, text="   JPEG品質:").pack(side=tk.LEFT)
        self.jpg_var = tk.IntVar(value=s.jpg_quality)
        sp = ttk.Spinbox(row, from_=30, to=100, increment=5, width=5, textvariable=self.jpg_var,
                         command=self._update_preview)
        sp.pack(side=tk.LEFT)
        sp.bind("<KeyRelease>", lambda ev: self._update_preview())
        chk(box, "cheat_codes", "チートコード対応 (CHEAT_CODES)")
        chk(box, "screenshot", "スクリーンショット機能 (外部フラッシュを150KB使用)")
        chk(box, "disable_splash", "起動時のロゴを表示しない")
        chk(box, "clean_build", "毎回クリーンビルドする (設定変更時は推奨)")
        row = ttk.Frame(box)
        row.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(row, text="追加の make 変数:").pack(side=tk.LEFT)
        self.extra_var = tk.StringVar(value=s.extra_retrogo_args)
        e = ttk.Entry(row, textvariable=self.extra_var)
        e.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        e.bind("<KeyRelease>", lambda ev: self._update_preview())

        box = ttk.LabelFrame(f, text="実行されるパラメータ", padding=8)
        box.pack(fill=tk.BOTH, expand=True, pady=8)
        self.preview = tk.Text(box, height=5, font=("Consolas", 9), wrap=tk.WORD, relief=tk.FLAT,
                               background=self.cget("background"))
        self.preview.pack(fill=tk.BOTH, expand=True)
        self._update_preview()

    def _collect_settings(self) -> None:
        s = self.settings
        s.backup_dir = self.backup_var.get()
        s.flash_mb = int(self.flash_var.get())
        for k, v in self.opt_vars.items():
            setattr(s, k, bool(v.get()))
        inv = {v: k for k, v in C.CODEPAGES.items()}
        s.codepage = inv.get(self.cp_var.get(), s.codepage)
        s.extra_retrogo_args = self.extra_var.get().strip()
        try:
            s.jpg_quality = min(max(int(self.jpg_var.get()), 1), 100)
        except (tk.TclError, ValueError):
            pass

    def _update_preview(self) -> None:
        self._collect_settings()
        s = self.settings
        self.preview.configure(state=tk.NORMAL)
        self.preview.delete("1.0", tk.END)
        size, offset = s.extflash_layout()
        self.preview.insert(tk.END, f'[パッチ]   make PATCH_PARAMS="{s.patch_params()}" patch\n')
        self.preview.insert(tk.END, f"[Retro-Go] make -j{self._jobs()} {' '.join(s.retrogo_vars())}\n")
        self.preview.insert(tk.END, f"[書き込み] gnwmanager で ③ 0x08100000 / ④ 外部 +{offset} を1回の接続で書き込み\n")
        self.preview.insert(tk.END, f"ROM用の容量: {s.retrogo_capacity() / 1024 / 1024:.1f} MB")
        self.preview.configure(state=tk.DISABLED)
        self._update_regions()
        if s.is_stock_flash:
            self.lite_note.pack(anchor=tk.W)
        else:
            self.lite_note.pack_forget()
        if s.is_stock_flash:
            self.keep_extras_cb.state(["disabled"])
            self.mario_note.configure(text=(
                "※ 純正1MBでは --internal-only で純正ファームを内部フラッシュに収め、外部フラッシュ全体を Retro-Go に使います。\n"
                "　 スリープ画像とマリオの歌の隠し要素は削除され、Retro-Go 起動後はハイスコア・明るさ/音量設定が保持されません。"))
        else:
            self.keep_extras_cb.state(["!disabled"])
            self.mario_note.configure(text=(
                "※ チェックなし: --internal-only（外部フラッシュ全体を Retro-Go に使用、隠し要素とハイスコア保存は無し）\n"
                "　 チェックあり: 純正データを外部フラッシュ先頭1MBに置き、Retro-Go は残りを使用"))

    def _update_regions(self) -> None:
        if not hasattr(self, "stock_regions"):
            return
        s = self.settings
        size, offset = s.extflash_layout()
        mb = 1024 * 1024
        if s.device == "mario" and not s.mario_uses_ext():
            stock = "② 内部 Bank1 (256KB): パッチ済み純正ファーム　※ --internal-only のため①（外部フラッシュ）は使いません"
        else:
            stock = (f"① 外部 0〜{s.dev['stock_mb'] if s.device == 'zelda' else 1}MB: 純正データ\n"
                     "② 内部 Bank1 (128KB): パッチ済み純正ファーム（十字キー左 + GAME の切り替え処理を含む）")
        end = offset + size
        rg = ("③ 内部 Bank2: Retro-Go 本体・ROM一覧\n"
              f"④ 外部 {offset / mb:g}MB〜{end / mb:g}MB: フォント・エミュレータ・ROM・カバー画像")
        self.stock_regions.configure(text=stock)
        self.rg_regions.configure(text=rg)
        self._update_write_buttons()

    def _update_write_buttons(self) -> None:
        if not hasattr(self, "write_btn"):
            return
        any_sel = self.write_stock_var.get() or self.write_rg_var.get()
        busy = self.worker is not None and self.worker.is_alive()
        state = tk.NORMAL if any_sel and not busy else tk.DISABLED
        self.write_btn.configure(state=state)
        self.build_btn.configure(state=state)
        self.settings.write_stock = bool(self.write_stock_var.get())
        self.settings.write_retrogo = bool(self.write_rg_var.get())
        if hasattr(self, "migrate_var"):
            self.settings.migrate_saves = bool(self.migrate_var.get())


    # ================================================================ TAB 4
    SEG_COLORS = [("固定データ", "#8c959f"), ("エミュレータ", "#8250df"), ("ROM", "#0969da"),
                  ("カバー画像", "#1f883d"), ("セーブ領域", "#bc4c00"), ("予約", "#57606a")]

    def _tab_roms(self) -> None:
        T.ensure_roms_dirs()
        f = ttk.Frame(self.nb, padding=12)
        self.nb.add(f, text=" ④ ROM と容量 ")
        ttk.Label(f, text="ROMフォルダと書き込み容量チェック", style="H.TLabel").pack(anchor=tk.W)
        ttk.Label(f, text=f"{C.ROMS} の機種別フォルダにROMを入れると自動で再計算します。"
                          "（ご自身が所有するソフトから吸い出したROMを使用してください）",
                  wraplength=900).pack(anchor=tk.W, pady=(2, 6))

        top = ttk.Frame(f)
        top.pack(fill=tk.X)
        ttk.Button(top, text="ROMフォルダを開く", command=lambda: os.startfile(C.ROMS)).pack(side=tk.LEFT)  # noqa: S606
        ttk.Label(top, text="  追加先:").pack(side=tk.LEFT)
        self.sys_var = tk.StringVar()
        self.sys_labels = [f"{name} [{folder}] {ext}" for folder, name, ext in C.ROM_SYSTEMS]
        cb = ttk.Combobox(top, textvariable=self.sys_var, values=self.sys_labels, state="readonly", width=40)
        cb.current(0)
        cb.pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="ROMを追加…", command=self.add_roms).pack(side=tk.LEFT)
        ttk.Button(top, text="選択を削除", command=self.remove_roms).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="カバーを編集…", command=self.edit_cover).pack(side=tk.LEFT)
        ttk.Button(top, text="カバー削除", command=self.remove_cover).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="再計算", command=lambda: self.request_estimate(force=True)).pack(side=tk.LEFT)
        self._btn(top, "試しビルドで正確に確認", self.do_exact_check, side=tk.RIGHT)

        cap = ttk.LabelFrame(f, text="外部フラッシュ (Retro-Go 領域)", padding=8)
        cap.pack(fill=tk.X, pady=8)
        self.verdict = tk.Label(cap, text="計算中…", font=("Yu Gothic UI", 13, "bold"), anchor=tk.W)
        self.verdict.pack(anchor=tk.W)
        self.bar = tk.Canvas(cap, height=26, highlightthickness=1, highlightbackground="#d0d7de", background="#f6f8fa")
        self.bar.pack(fill=tk.X, pady=6)
        self.bar.bind("<Configure>", lambda e: self._draw_bar())
        legend = ttk.Frame(cap)
        legend.pack(fill=tk.X)
        self.legend_vars: dict[str, tk.StringVar] = {}
        for name, color in self.SEG_COLORS + [("空き", "#f6f8fa")]:
            cell = ttk.Frame(legend)
            cell.pack(side=tk.LEFT, padx=(0, 12))
            tk.Label(cell, width=2, background=color, relief=tk.SOLID, borderwidth=1).pack(side=tk.LEFT)
            v = tk.StringVar(value=name)
            self.legend_vars[name] = v
            ttk.Label(cell, textvariable=v).pack(side=tk.LEFT, padx=3)
        self.detail_var = tk.StringVar()
        ttk.Label(cap, textvariable=self.detail_var, foreground="#57606a", justify=tk.LEFT).pack(anchor=tk.W, pady=(4, 0))
        self.exact_var = tk.StringVar(value="試しビルド結果: 未実行（上の見積もりは実ビルドと照合済みの計算式によるものです）")
        self.exact_label = tk.Label(cap, textvariable=self.exact_var, anchor=tk.W)
        self.exact_label.pack(anchor=tk.W, pady=(4, 0))

        cols = ("size", "stored", "save", "cover", "note")
        tf = ttk.Frame(f)
        tf.pack(fill=tk.BOTH, expand=True)
        prev = ttk.LabelFrame(tf, text="カバー (実機での見え方)", padding=6)
        prev.pack(side=tk.RIGHT, fill=tk.Y, padx=(8, 0))
        self.cover_canvas = tk.Canvas(prev, width=184, height=140, background="#000000", highlightthickness=0,
                                      cursor="hand2")
        self.cover_canvas.pack()
        self.cover_canvas.bind("<Button-1>", lambda e: self.edit_cover())
        self.cover_info = ttk.Label(prev, text="ROMを選択すると\n表示します", justify=tk.LEFT, wraplength=184)
        self.cover_info.pack(anchor=tk.W, pady=(6, 0))
        ttk.Label(prev, foreground="#57606a", justify=tk.LEFT, wraplength=184, text=(
            "クリック / ROMをダブルクリック: 編集\nROMを選んで Ctrl+V: 画像を貼り付けて編集")).pack(anchor=tk.W, pady=(8, 0))
        self._cover_photo = None
        self.rom_tree = ttk.Treeview(tf, columns=cols, selectmode="extended")
        self.rom_tree.bind("<<TreeviewSelect>>", lambda e: self._show_cover_preview())
        self.rom_tree.bind("<Double-1>", lambda e: self.edit_cover())
        self.rom_tree.bind("<Control-v>", lambda e: self.edit_cover(paste=True))
        self.rom_tree.bind("<Control-V>", lambda e: self.edit_cover(paste=True))
        for c, text, w, anchor in (("#0", "機種 / ファイル", 280, tk.W), ("size", "元サイズ", 80, tk.E),
                                   ("stored", "書き込みサイズ", 100, tk.E), ("save", "セーブ領域", 80, tk.E),
                                   ("cover", "カバー", 90, tk.E), ("note", "備考", 200, tk.W)):
            self.rom_tree.heading(c, text=text)
            self.rom_tree.column(c, width=w, anchor=anchor)
        sb = ttk.Scrollbar(tf, orient=tk.VERTICAL, command=self.rom_tree.yview)
        self.rom_tree.configure(yscrollcommand=sb.set)
        self.rom_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.LEFT, fill=tk.Y)
        self.rom_tree.tag_configure("warn", foreground="#cf222e")

        self.estimator = Estimator()
        self.estimate: Optional[Estimate] = None
        self._segments: list[int] = []
        self._est_sig = None
        self._est_running = False
        self._est_pending = False
        self.after(500, self._watch_roms)

    @staticmethod
    def _fmt(n: int) -> str:
        if abs(n) >= 1024 * 1024:
            return f"{n / 1024 / 1024:.2f} MB"
        if abs(n) < 1024:
            return f"{n} B"
        return f"{n / 1024:,.0f} KB"

    def _watch_roms(self) -> None:
        try:
            sig = (self.estimator.signature(C.ROMS), self._settings_sig())
            if sig != self._est_sig:
                self._est_sig = sig
                self.request_estimate()
        except OSError:
            pass
        self.after(2000, self._watch_roms)

    def _settings_sig(self) -> tuple:
        s = self.settings
        return (s.device, s.flash_mb, s.mario_keep_extras, s.codepage, s.coverflow, s.jpg_quality,
                s.state_saving, s.screenshot)

    def refresh_roms(self) -> None:
        if hasattr(self, "estimator"):
            self.request_estimate()

    def request_estimate(self, force: bool = False) -> None:
        if force:
            self.estimator = Estimator()
        if self._est_running:
            self._est_pending = True
            return
        self._est_running = True
        self.verdict.configure(text="計算中… (ROMを圧縮して実サイズを算出しています)", foreground="#57606a")
        settings = C.Settings(**{k: getattr(self.settings, k) for k in C.Settings.__dataclass_fields__})
        py = C.VENV_PY if C.VENV_PY.exists() else None
        estimator = self.estimator

        def work():
            try:
                est = estimator.estimate(C.ROMS, settings, py)
                self.after(0, lambda: self._show_estimate(est))
            except Exception as e:  # noqa: BLE001
                msg = str(e)
                self.after(0, lambda: self.verdict.configure(text=f"計算エラー: {msg}", foreground="#cf222e"))
            finally:
                self.after(0, self._estimate_done)
        threading.Thread(target=work, daemon=True).start()

    def _estimate_done(self) -> None:
        self._est_running = False
        if self._est_pending:
            self._est_pending = False
            self.request_estimate()

    def _show_estimate(self, est: Estimate) -> None:
        self.estimate = est
        tree = self.rom_tree
        # 再計算のたびに一覧を作り直すため、選択とスクロール位置を引き継ぐ
        prev_sel, prev_y = tree.selection(), tree.yview()[0]
        tree.delete(*tree.get_children())
        names = {folder: name for folder, name, _ in C.ROM_SYSTEMS}
        groups: dict[str, list] = {}
        for r in est.roms:
            groups.setdefault(r.folder, []).append(r)
        cf = self.settings.coverflow
        for folder, roms in groups.items():
            ncov = sum(1 for r in roms if r.cover)
            parent = tree.insert("", tk.END, iid=f"sys:{folder}", open=True,
                                 text=f"{names[folder]}  ({len(roms)})",
                                 values=(self._fmt(sum(r.size for r in roms)),
                                         self._fmt(sum(r.stored for r in roms if not r.note)),
                                         self._fmt(sum(r.save for r in roms if not r.note)),
                                         f"{ncov}/{len(roms)} 枚", ""))
            for r in roms:
                note = r.note or (f"圧縮 {r.stored * 100 // max(r.size, 1)}%" if r.compressed else "非圧縮")
                if not r.cover:
                    cov = "なし"
                elif r.cover_bytes < 0:
                    cov = "変換失敗"
                    note = "カバー画像を読み込めません"
                else:
                    cov = self._fmt(r.cover_bytes) if cf else f"({self._fmt(r.cover_bytes)})"
                tree.insert(parent, tk.END, iid=str(r.path), text=r.path.name,
                            values=(self._fmt(r.size), self._fmt(r.stored), self._fmt(r.save), cov, note),
                            tags=("warn",) if r.note or cov == "変換失敗" else ())
        if est.orphan_images:
            parent = tree.insert("", tk.END, iid="sys:_orphan", open=True,
                                 text=f"対応するROMが無い画像  ({len(est.orphan_images)})", tags=("warn",))
            for img in est.orphan_images:
                tree.insert(parent, tk.END, iid=str(img), text=img.name, tags=("warn",),
                            values=(self._fmt(img.stat().st_size), "—", "—", "—",
                                    "ROMと同じファイル名にしてください"))
        keep = [i for i in prev_sel if tree.exists(i)]
        if keep:
            tree.selection_set(keep)
            tree.focus(keep[0])
        tree.yview_moveto(prev_y)

        if est.problems:
            self.verdict.configure(text="✖ " + " / ".join(est.problems), foreground="#cf222e")
        elif est.fits:
            extra = "（余裕が少ないため試しビルドでの確認を推奨）" if est.tight else ""
            self.verdict.configure(text=f"✔ 入ります　残り {self._fmt(est.free)} {extra}",
                                   foreground="#9a6700" if est.tight else "#1a7f37")
        else:
            self.verdict.configure(text=f"✖ 入りません　{self._fmt(-est.free)} 超過しています", foreground="#cf222e")

        self._segments = [est.base, est.emu_code, est.rom_data, est.images, est.saves, est.reserved]
        for (name, _), val in zip(self.SEG_COLORS, self._segments):
            self.legend_vars[name].set(f"{name} {self._fmt(val)}")
        self.legend_vars["空き"].set(f"空き {self._fmt(max(est.free, 0))}")
        self._draw_bar()
        ncov = sum(1 for r in est.roms if r.cover)
        cover_txt = ""
        if ncov and not self.settings.coverflow:
            cover_txt = f"\nカバー画像 {ncov} 枚あり — ③構成で「カバーアート表示」を有効にすると使われます（括弧内は有効時のサイズ）"
        elif self.settings.coverflow:
            cover_txt = f"\nカバー画像 {ncov}/{len(est.roms)} 本に設定済み（画像が無いROMはカバー無しで表示されます）"
        self.detail_var.set(
            f"Retro-Go 用領域 {self._fmt(est.total)}（外部フラッシュ {self.settings.flash_mb}MB 構成）"
            f"　ROM {len([r for r in est.roms if not r.note])} 本 / 元サイズ合計 {self._fmt(sum(r.size for r in est.roms))}"
            + cover_txt
            + ("\n※ MSX/Amstradのエミュレータサイズは推定値です" if est.emu_estimated else "")
            + "".join(f"\n⚠ {w}" for w in est.warnings))
        self._show_cover_preview()

    def _draw_bar(self) -> None:
        c = self.bar
        c.delete("all")
        est = self.estimate
        if not est or est.total <= 0:
            return
        w, h = c.winfo_width(), c.winfo_height()
        scale = w / max(est.total, est.usage + est.saves + est.reserved)
        x = 0.0
        for (_, color), val in zip(self.SEG_COLORS, self._segments):
            if val <= 0:
                continue
            nx = x + max(val * scale, 2)
            c.create_rectangle(x, 0, nx, h, fill=color, width=0)
            x = nx
        if not est.fits:
            lim = est.total * scale
            c.create_line(lim, 0, lim, h, fill="#cf222e", width=3)

    def _sys_folder(self) -> str:
        try:
            return C.ROM_SYSTEMS[self.sys_labels.index(self.sys_var.get())][0]
        except ValueError:
            return C.ROM_SYSTEMS[0][0]

    def add_roms(self) -> None:
        folder = self._sys_folder()
        files = filedialog.askopenfilenames(title=f"ROMを選択 → roms\\{folder}")
        if not files:
            return
        dest = C.ROMS / folder
        dest.mkdir(parents=True, exist_ok=True)
        for src in files:
            shutil.copy2(src, dest / Path(src).name)
            self.log(f"追加: {Path(src).name} → roms/{folder}/")
        self.request_estimate()

    def remove_roms(self) -> None:
        sel = [i for i in self.rom_tree.selection() if not i.startswith("sys:")]
        if not sel or not messagebox.askyesno(
                C.APP_NAME, f"{len(sel)} 個のファイルを roms フォルダから削除しますか？\n（ROMのカバー画像も一緒に削除します）"):
            return
        for iid in sel:
            p = Path(iid)
            if p.suffix.lower() not in ALL_COVER_SUFFIXES:
                self._delete_covers(p)
            p.unlink(missing_ok=True)
            self.log(f"削除: {p.name}")
        self.request_estimate()

    def _selected_rom(self) -> Optional[Path]:
        sel = [i for i in self.rom_tree.selection() if not i.startswith("sys:")]
        if not sel:
            return None
        p = Path(sel[0])
        return p if p.suffix.lower() not in ALL_COVER_SUFFIXES else None

    def edit_cover(self, paste: bool = False) -> None:
        rom = self._selected_rom()
        if not rom:
            messagebox.showinfo(C.APP_NAME, "カバーを編集するROMを一覧から選んでください。")
            return
        self._collect_settings()

        def saved() -> None:
            self.log(f"カバー更新: {rom.name}")
            self.request_estimate()
            self.after(300, self._show_cover_preview)
        CE.open_editor(self, rom, self.settings, saved, paste=paste)

    def remove_cover(self) -> None:
        rom = self._selected_rom()
        if rom and (find_cover(rom) or CE.find_original(rom)) and \
                messagebox.askyesno(C.APP_NAME, f"{rom.name} のカバー画像（元画像を含む）を削除しますか？"):
            self._delete_covers(rom)
            self.request_estimate()

    def _delete_covers(self, rom: Path) -> None:
        # 優先順位の高い拡張子が残っていると新しい画像が使われないため、同名の画像はすべて消す
        for c in CE.delete_cover_files(rom, originals=True):
            self.log(f"カバー削除: {c.name}")

    def _show_cover_preview(self) -> None:
        c = self.cover_canvas
        c.delete("all")
        self._cover_photo = None
        sel = [i for i in self.rom_tree.selection() if not i.startswith("sys:")]
        if not sel:
            self.cover_info.configure(text="ROMを選択すると\n表示します")
            return
        p = Path(sel[0])
        if p.suffix.lower() in ALL_COVER_SUFFIXES:
            img_path, folder = p, p.parent.name
        else:
            img_path, folder = find_cover(p), p.parent.name
        if not img_path:
            c.create_text(92, 70, text="カバーなし", fill="#8c959f")
            self.cover_info.configure(text="カバーなし")
            return
        w, h = cover_dims(folder)
        try:
            from PIL import Image, ImageTk
            img = Image.open(img_path).convert("RGB")
            orig = img.size
            img = img.resize((w, h), Image.Resampling.LANCZOS)
            self._cover_photo = ImageTk.PhotoImage(img)
            c.create_image(92, 70, image=self._cover_photo)
            ratio = orig[0] / max(orig[1], 1)
            warn = "\n⚠ 縦横比が 4:3 と異なるため歪みます" if abs(ratio - w / h) > 0.15 else ""
            self.cover_info.configure(text=f"{img_path.name}\n元 {orig[0]}×{orig[1]} → {w}×{h}{warn}")
        except ImportError:
            c.create_text(92, 70, text="(プレビューには Pillow が必要)", fill="#8c959f")
            self.cover_info.configure(text=img_path.name)
        except Exception as e:  # noqa: BLE001
            c.create_text(92, 70, text="読み込めません", fill="#cf222e")
            self.cover_info.configure(text=f"{img_path.name}\n{e}")

    def do_exact_check(self) -> None:
        if not self._check_ready(need_backup=False, need_roms=True):
            return
        self.run_steps("試しビルド", self._rg_steps(False))

    def _apply_build_result(self, lines: list[str]) -> None:
        usage = parse_build_usage(lines)
        overflow = parse_overflow(lines)
        stamp = time.strftime("%H:%M")
        if overflow:
            txt = ", ".join(f"{r} を {self._fmt(n)} 超過" for r, n in overflow)
            self.exact_var.set(f"試しビルド結果 ({stamp}): ✖ 入りません — {txt}")
            self.exact_label.configure(foreground="#cf222e")
        elif usage:
            self.exact_var.set(
                f"試しビルド結果 ({stamp}): ✔ 入ります — 使用 {self._fmt(usage['usage'])} / "
                f"容量 {self._fmt(usage['capacity'])}（セーブ領域除く）/ 残り {self._fmt(usage['free'])}")
            self.exact_label.configure(foreground="#1a7f37")

    # ================================================================ TAB 5
    def _tab_flash(self) -> None:
        f = ttk.Frame(self.nb, padding=12)
        self.nb.add(f, text=" ⑤ ビルド & 書き込み ")
        ttk.Label(f, text="ST-Link を接続し、本体の電源を入れた状態で実行してください", style="H.TLabel").pack(anchor=tk.W)

        main = ttk.LabelFrame(f, text="書き込む内容", padding=10)
        main.pack(fill=tk.X, pady=(8, 4))
        self.write_stock_var = tk.BooleanVar(value=self.settings.write_stock)
        self.write_rg_var = tk.BooleanVar(value=self.settings.write_retrogo)
        for var, title, attr in ((self.write_stock_var, "純正ファーム", "stock_regions"),
                                 (self.write_rg_var, "Retro-Go", "rg_regions")):
            row = ttk.Frame(main)
            row.pack(fill=tk.X, pady=2)
            cb = ttk.Checkbutton(row, text=title, variable=var, width=14, command=self._update_write_buttons)
            cb.pack(side=tk.LEFT, anchor=tk.N)
            self.busy_widgets.append(cb)
            lab = ttk.Label(row, justify=tk.LEFT)
            lab.pack(side=tk.LEFT, anchor=tk.W)
            setattr(self, attr, lab)
        ttk.Label(main, foreground="#57606a", justify=tk.LEFT, text=(
            "・改造済みの本体で ROM や設定を変えたときは「Retro-Go」だけで十分です。初めて改造する本体は両方にチェックしてください。\n"
            "・③④は同じビルドの組でしか動かないため、分けずに1つの保存ファイル（builds\\*.gnw）にまとめて扱います。"
        )).pack(anchor=tk.W, pady=(6, 4))
        self.migrate_var = tk.BooleanVar(value=self.settings.migrate_saves)
        cb = ttk.Checkbutton(main, variable=self.migrate_var, command=self._update_write_buttons, text=(
            "セーブ位置が変わる場合はセーブデータを引き継ぐ（前のビルドで吸い出し → 書き込み → ROM名で書き戻し）"))
        cb.pack(anchor=tk.W, pady=(0, 6))
        self.busy_widgets.append(cb)
        row = ttk.Frame(main)
        row.pack(fill=tk.X)
        self.write_btn = self._btn(row, "ビルドして書き込む", self.do_write, style="Big.TButton",
                                   side=tk.LEFT, fill=tk.X, expand=True)
        self.build_btn = self._btn(row, "ビルドして保存のみ", self.do_build_only, side=tk.LEFT, padx=(8, 0))
        self.boot_hint = ttk.Label(main, foreground="#57606a")
        self.boot_hint.pack(anchor=tk.W, pady=(6, 0))

        saved = ttk.LabelFrame(f, text="保存済みビルド（★ = この本体に最後に書き込んだもの）", padding=10)
        saved.pack(fill=tk.BOTH, expand=True, pady=4)
        tf = ttk.Frame(saved)
        tf.pack(fill=tk.BOTH, expand=True)
        cols = ("device", "content", "flash", "cp")
        self.build_tree = ttk.Treeview(tf, columns=cols, height=5, selectmode="browse")
        for c, text, w in (("#0", "作成日時", 190), ("device", "本体", 150), ("content", "内容", 230),
                           ("flash", "外部フラッシュ", 100), ("cp", "言語 / カバー", 130)):
            self.build_tree.heading(c, text=text)
            self.build_tree.column(c, width=w, anchor=tk.W)
        sb = ttk.Scrollbar(tf, orient=tk.VERTICAL, command=self.build_tree.yview)
        self.build_tree.configure(yscrollcommand=sb.set)
        self.build_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.LEFT, fill=tk.Y)
        self.build_tree.tag_configure("other", foreground="#8c959f")
        self.build_tree.tag_configure("current", foreground="#1a7f37")
        self.build_tree.bind("<Double-1>", lambda e: self.show_build_detail())
        row = ttk.Frame(saved)
        row.pack(fill=tk.X, pady=(6, 0))
        self._btn(row, "選んだビルドを書き込む", self.do_write_saved, side=tk.LEFT)
        ttk.Button(row, text="詳細 (ROM一覧)", command=self.show_build_detail).pack(side=tk.LEFT, padx=6)
        self._btn(row, "削除", self.delete_build, side=tk.LEFT)
        ttk.Button(row, text="ファイルから追加…", command=self.import_build).pack(side=tk.LEFT, padx=6)
        ttk.Button(row, text="フォルダを開く",
                   command=lambda: (P.BUILDS.mkdir(exist_ok=True), os.startfile(P.BUILDS))).pack(side=tk.LEFT)  # noqa: S606

        tools = ttk.LabelFrame(f, text="ツール", padding=10)
        tools.pack(fill=tk.X, pady=4)
        self._btn(tools, "接続確認", self.do_info, side=tk.LEFT)
        self._btn(tools, "セーブデータをPCへバックアップ", self.do_save_backup, side=tk.LEFT, padx=6)
        self._btn(tools, "セーブデータを書き戻す…", self.do_save_restore, side=tk.LEFT)
        self._btn(tools, "純正ファームに戻す", self.do_restore_stock, side=tk.LEFT, padx=6)

        ctl = ttk.LabelFrame(f, text="Retro-Go の操作 (この本体の場合)", padding=10)
        ctl.pack(fill=tk.X)
        self.controls_label = ttk.Label(ctl, justify=tk.LEFT)
        self.controls_label.pack(anchor=tk.W)
        ttk.Label(ctl, foreground="#57606a", justify=tk.LEFT, text=(
            "PAUSE/SET + A: ステートセーブ / PAUSE/SET + B: ステートロード / PAUSE/SET + 十字キー: 明るさ・音量"
        )).pack(anchor=tk.W, pady=(4, 0))
        self.after(300, self.refresh_builds)

    # -------------------------------------------------------- saved builds
    def refresh_builds(self) -> None:
        if not hasattr(self, "build_tree"):
            return
        tree = self.build_tree
        tree.delete(*tree.get_children())
        current = self.settings.last_written.get(self.settings.device, {}).get("package")
        for path, m in P.list_packages():
            rg = m.get("retrogo") or {}
            cp = C.CODEPAGES.get(str(rg.get("codepage", "")), "").split(" ")[0] if rg else ""
            cov = " / カバーあり" if rg.get("coverflow") else ""
            is_cur = path.name == current
            tags = ("current",) if is_cur else (() if m["device"] == self.settings.device else ("other",))
            tree.insert("", tk.END, iid=str(path), text=("★ " if is_cur else "　") + m["created"],
                        values=(m["device_name"], P.describe(m), f"{m['flash_mb']}MB", cp + cov), tags=tags)

    def _selected_build(self) -> Optional[Path]:
        sel = self.build_tree.selection()
        if not sel:
            messagebox.showinfo(C.APP_NAME, "保存済みビルドを一覧から選んでください。")
            return None
        return Path(sel[0])

    def show_build_detail(self) -> None:
        path = self._selected_build()
        if not path:
            return
        m = P.read_manifest(path)
        lines = [f"ファイル: {path.name}", f"作成: {m['created']}", f"本体: {m['device_name']}版 / 外部フラッシュ {m['flash_mb']}MB"]
        if m.get("stock"):
            lines.append(f"純正パッチ: {m['stock']['patch_params']}")
        if m.get("retrogo"):
            rg = m["retrogo"]
            lines.append(f"Retro-Go: 外部 {rg['extflash_offset'] // 1024}KB目から {rg['extflash_size'] // 1024}KB")
            lines.append(f"ROM {len(m['roms'])} 本:")
            names = {folder: name for folder, name, _ in C.ROM_SYSTEMS}
            lines += [f"  [{names.get(r['system'], r['system'])}] {r['file']}" for r in m["roms"][:60]]
            if len(m["roms"]) > 60:
                lines.append(f"  … ほか {len(m['roms']) - 60} 本")
        messagebox.showinfo(C.APP_NAME, "\n".join(lines))

    def delete_build(self) -> None:
        path = self._selected_build()
        if path and messagebox.askyesno(C.APP_NAME, f"{path.name} を削除しますか？"):
            path.unlink(missing_ok=True)
            self.refresh_builds()

    def import_build(self) -> None:
        src = filedialog.askopenfilename(title="保存ビルドを追加", filetypes=[("保存ビルド", "*.gnw")])
        if not src:
            return
        try:
            P.read_manifest(Path(src))
        except Exception as e:  # noqa: BLE001
            messagebox.showerror(C.APP_NAME, f"保存ビルドとして読み込めません: {e}")
            return
        P.BUILDS.mkdir(exist_ok=True)
        shutil.copy2(src, P.BUILDS / Path(src).name)
        self.refresh_builds()

    # -------------------------------------------------------------- actions
    def _check_ready(self, need_backup: bool = True, need_roms: bool = False) -> bool:
        self._collect_settings()
        if not all(ok for ok, _ in T.status().values()):
            messagebox.showwarning(C.APP_NAME, "環境が整っていません。① 環境セットアップ を実行してください。")
            self.nb.select(0)
            return False
        if need_backup and not self.verify_backup():
            messagebox.showwarning(C.APP_NAME, "バックアップの検証に失敗しました。② バックアップ を確認してください。")
            self.nb.select(1)
            return False
        if need_roms:
            est = self.estimate
            if est is None or est.problems:
                msg = " / ".join(est.problems) if est else "容量の計算が終わっていません。少し待ってから再実行してください。"
                messagebox.showwarning(C.APP_NAME, msg)
                self.nb.select(3)
                return False
            if not est.fits and not messagebox.askyesno(C.APP_NAME, (
                    f"見積もりでは {self._fmt(-est.free)} 容量を超過しています。\n"
                    "ビルドはリンク時に失敗する可能性が高いです。続行しますか？")):
                self.nb.select(3)
                return False
        return True

    def _confirm_flash(self, what: str) -> bool:
        return messagebox.askokcancel(C.APP_NAME, (
            f"{what}\n\n"
            "・ST-Link が GND/SWDIO/SWCLK で接続されていること\n"
            "・本体の電源が入っていること（電池残量十分）\n"
            "・書き込み中はケーブルを抜かないこと\n\nを確認して「OK」を押してください。"
        ), icon=messagebox.WARNING)

    def _copy_backups_step(self) -> Step:
        src = Path(self.settings.backup_dir)

        def fn(log, hook):
            for name in C.backup_names(self.settings.device):
                shutil.copy2(src / name, C.PATCH_REPO / name)
                log(f"コピー: {name} → game-and-watch-patch/")
        return ("バックアップをパッチ作業フォルダへコピー", fn)

    def _patch_steps(self) -> list[Step]:
        params = self.settings.patch_params()
        return [
            ("ビルド環境の準備", lambda log, hook: T.write_shims()),
            self._copy_backups_step(),
            ("パッチをクリーン", self.sh("make clean", C.PATCH_REPO)),
            (f"パッチ作成 ({params})", self.sh(f"make PATCH_PARAMS={shlex.quote(params)} patch", C.PATCH_REPO)),
        ]

    def _rg_steps(self) -> list[Step]:
        s = self.settings
        vars_ = " ".join(shlex.quote(v) for v in s.retrogo_vars())
        steps: list[Step] = [("ビルド環境の準備", lambda log, hook: T.write_shims()),
                             ("ROMフォルダを retro-go に同期", T.sync_roms)]
        if s.clean_build:
            steps.append(("Retro-Go をクリーン", self.sh(f"make {vars_} clean", C.RETROGO_REPO)))
        steps.append(("Retro-Go をビルド (数分かかります)", self.sh(f"make -j{self._jobs()} {vars_}", C.RETROGO_REPO)))
        return steps

    def _build_and_save_steps(self, ctx: dict, stock: bool, rg: bool) -> list[Step]:
        settings = self.settings

        def save(log, hook):
            ctx["pkg"] = P.create(settings, stock, rg, log)
        return (self._patch_steps() if stock else []) + (self._rg_steps() if rg else []) + [
            ("ビルドを保存", save)]

    def _run_bash(self, cmd: str, cwd: Path, log, hook) -> None:
        T.run_cmd([str(T.bash_exe()), "-c", cmd], log, cwd=cwd, proc_hook=hook)

    def _write_package_steps(self, ctx: dict, stock: bool, rg: bool) -> list[Step]:
        """保存ビルド (ctx['pkg']) を検証して書き込む。ビルド直後でも後からでも同じ手順."""
        settings = self.settings
        device = settings.device
        migrate = bool(self.migrate_var.get())

        def unpack(log, hook):
            ctx["work"] = P.new_workdir()
            m = P.extract(ctx["pkg"], ctx["work"])
            chk = P.check(m, settings, stock, rg)
            for w in chk.warnings:
                log(f"注意: {w}")
            if chk.errors:
                raise RuntimeError(" / ".join(chk.errors))
            ctx["m"] = m
            log(f"検証OK: {ctx['pkg'].name}（{P.describe(m)}）")

        def check_saves(log, hook):
            new_slots = P.save_slots(ctx["work"] / P.RG_ELF)
            ctx["new_slots"] = new_slots
            rec = settings.last_written.get(device)
            old_pkg = P.BUILDS / rec["package"] if rec else None
            old_elf = P.elf_of(old_pkg, ctx["work"] / "old") if old_pkg and old_pkg.exists() else None
            if old_elf is None:
                log("注意: この本体に前回書き込んだビルドが分からないため、セーブ位置の比較をスキップします")
                return
            old_slots = P.save_slots(old_elf)
            if P.same_save_layout(old_slots, new_slots):
                log("セーブデータの位置は前回と同じです（引き継ぎ不要）")
                return
            if not migrate:
                log("注意: セーブデータの位置が変わります（引き継ぎは無効に設定されています）")
                return
            out = P.SAVES / device / (time.strftime("%Y%m%d-%H%M%S") + "_書き込み前")
            for s in old_slots:
                (out / s.filename).parent.mkdir(parents=True, exist_ok=True)
            log(f"セーブ位置が変わるため、現在のセーブ {len(old_slots)} 件を吸い出します → {out}")
            if old_slots:
                self._run_bash(P.backup_command(old_slots, out), C.ROOT, log, hook)
            ctx["restore_from"] = out

        def write(log, hook):
            self._run_bash(P.flash_command(ctx["work"], ctx["m"], stock, rg), C.ROOT, log, hook)

        def restore(log, hook):
            src = ctx.get("restore_from")
            if not src:
                return
            cmd, restored = P.restore_command(ctx["new_slots"], src)
            if cmd:
                self._run_bash(cmd, C.ROOT, log, hook)
            log(f"セーブデータを {len(restored)} 件引き継ぎました" + (": " + ", ".join(restored) if restored else ""))

        def finish(log, hook):
            if rg:
                self._run_bash(P.reset_dbgmcu_command(), C.RETROGO_REPO, log, hook)
                settings.last_written[device] = {"package": ctx["pkg"].name,
                                                 "written": time.strftime("%Y-%m-%d %H:%M:%S")}
                settings.save()
            P.remove_workdir(ctx["work"])

        steps: list[Step] = [("保存ビルドを展開して検証", unpack)]
        if rg:
            steps.append(("セーブデータの位置を確認", check_saves))
        steps.append(("書き込み (1回の接続で選んだ領域をまとめて書き込み)", write))
        if rg:
            steps.append(("セーブデータを書き戻す", restore))
        steps.append(("後処理", finish))
        return steps

    def _selection(self) -> tuple[bool, bool]:
        return bool(self.write_stock_var.get()), bool(self.write_rg_var.get())

    def _selection_text(self, stock: bool, rg: bool) -> str:
        parts = []
        if stock:
            parts.append("純正ファーム（" + self.stock_regions.cget("text").replace("\n", " / ") + "）")
        if rg:
            parts.append("Retro-Go（" + self.rg_regions.cget("text").replace("\n", " / ") + "）")
        text = "\n".join("・" + p for p in parts)
        if rg and not self.settings.last_written.get(self.settings.device):
            text += ("\n\n※ この本体に前回書き込んだビルドの記録がありません。ROM構成が以前と違う場合、"
                     "既存のセーブデータが読めなくなることがあります。")
        return text

    def _cleanup(self, ctx: dict) -> Callable:
        """成功・失敗に関わらず展開用の一時フォルダを消してから on_done を呼ぶ."""
        def on_done(ok: bool) -> None:
            if "work" in ctx:
                P.remove_workdir(ctx["work"])
            self._done_message(ok)
        return on_done

    def _done_message(self, ok: bool) -> None:
        self.refresh_builds()
        if ok:
            messagebox.showinfo(C.APP_NAME, f"完了しました！\n通常起動で純正の{self.settings.dev['name']}、"
                                            "「十字キー左 + GAME」で Retro-Go が起動します。")

    def do_write(self) -> None:
        stock, rg = self._selection()
        if not (stock or rg) or not self._check_ready(need_backup=stock, need_roms=rg):
            return
        if not self._confirm_flash("次の内容をビルドして書き込みます。\n\n" + self._selection_text(stock, rg)):
            return
        ctx: dict = {}
        title = "書き込み (" + " + ".join(n for n, on in (("純正", stock), ("Retro-Go", rg)) if on) + ")"
        self.run_steps(title, self._build_and_save_steps(ctx, stock, rg) + self._write_package_steps(ctx, stock, rg),
                       on_done=self._cleanup(ctx))

    def do_build_only(self) -> None:
        stock, rg = self._selection()
        if not (stock or rg) or not self._check_ready(need_backup=stock, need_roms=rg):
            return
        self.run_steps("ビルドして保存", self._build_and_save_steps({}, stock, rg),
                       on_done=lambda ok: self.refresh_builds())

    def do_write_saved(self) -> None:
        path = self._selected_build()
        if not path:
            return
        self._collect_settings()
        m = P.read_manifest(path)
        want_stock, want_rg = self._selection()
        stock, rg = want_stock and bool(m.get("stock")), want_rg and bool(m.get("retrogo"))
        if not (stock or rg):
            messagebox.showinfo(C.APP_NAME, f"このビルドには、上でチェックした内容が含まれていません（含まれるもの: {P.describe(m)}）。")
            return
        chk = P.check(m, self.settings, stock, rg)
        if chk.errors:
            messagebox.showerror(C.APP_NAME, "このビルドは今の本体設定には書き込めません。\n\n・" + "\n・".join(chk.errors))
            return
        if not all(ok for ok, _ in T.status().values()):
            messagebox.showwarning(C.APP_NAME, "環境が整っていません。① 環境セットアップ を実行してください。")
            return
        warn = ("\n\n注意:\n・" + "\n・".join(chk.warnings)) if chk.warnings else ""
        if not self._confirm_flash(f"保存済みビルド {m['created']} を書き込みます。\n\n"
                                   + self._selection_text(stock, rg) + warn):
            return
        ctx = {"pkg": path}
        self.run_steps("保存済みビルドの書き込み", self._write_package_steps(ctx, stock, rg), on_done=self._cleanup(ctx))

    def do_info(self) -> None:
        if self._check_ready(need_backup=False):
            self.run_steps("接続確認", [("gnwmanager info", self.sh("gnwmanager info", C.ROOT))])

    def _current_slots_step(self, ctx: dict) -> Step:
        device = self.settings.device
        rec = self.settings.last_written.get(device)

        def fn(log, hook):
            pkg = P.BUILDS / rec["package"]
            ctx["work"] = P.new_workdir()
            elf = P.elf_of(pkg, ctx["work"])
            if elf is None:
                raise RuntimeError(f"{pkg.name} が見つかりません")
            ctx["slots"] = P.save_slots(elf)
            log(f"本体のビルド: {pkg.name} / セーブ {len(ctx['slots'])} 件")
        return ("本体に書き込まれているビルドからセーブ位置を取得", fn)

    def _need_record(self) -> bool:
        rec = self.settings.last_written.get(self.settings.device)
        if rec and (P.BUILDS / rec["package"]).exists():
            return True
        messagebox.showinfo(C.APP_NAME, (
            "この本体に書き込まれているビルドが分からないため、セーブデータの位置を特定できません。\n"
            "⑤で一度書き込むか、保存済みビルドを書き込むと使えるようになります。"))
        return False

    def do_save_backup(self) -> None:
        if not self._check_ready(need_backup=False) or not self._need_record():
            return
        ctx: dict = {}
        out = P.SAVES / self.settings.device / time.strftime("%Y%m%d-%H%M%S")

        def dump(log, hook):
            for s in ctx["slots"]:
                (out / s.filename).parent.mkdir(parents=True, exist_ok=True)
            if ctx["slots"]:
                self._run_bash(P.backup_command(ctx["slots"], out), C.ROOT, log, hook)
            self._run_bash(P.reset_dbgmcu_command(), C.RETROGO_REPO, log, hook)
            P.remove_workdir(ctx["work"])
            log(f"保存先: {out}")
        self.run_steps("セーブデータのバックアップ", [self._current_slots_step(ctx), ("吸い出し", dump)],
                       on_done=lambda ok: ok and out.exists() and os.startfile(out))  # noqa: S606

    def do_save_restore(self) -> None:
        if not self._check_ready(need_backup=False) or not self._need_record():
            return
        start = P.SAVES / self.settings.device
        start.mkdir(parents=True, exist_ok=True)
        src = filedialog.askdirectory(title="書き戻すセーブデータのフォルダ", initialdir=str(start))
        if not src or not self._confirm_flash(f"{src} のセーブデータを、ROM名が一致するゲームへ書き戻します。"):
            return
        ctx: dict = {}

        def write(log, hook):
            cmd, restored = P.restore_command(ctx["slots"], Path(src))
            if cmd:
                self._run_bash(cmd, C.ROOT, log, hook)
                self._run_bash(P.reset_dbgmcu_command(), C.RETROGO_REPO, log, hook)
            P.remove_workdir(ctx["work"])
            log(f"書き戻し {len(restored)} 件" + (": " + ", ".join(restored) if restored else "（一致するROMがありません）"))
        self.run_steps("セーブデータの書き戻し", [self._current_slots_step(ctx), ("書き戻し", write)])

    def do_restore_stock(self) -> None:
        if not self._check_ready():
            return
        if not self._confirm_flash(f"{self.settings.dev['name']}版の純正ファームをバックアップから書き戻し、Retro-Go(Bank2)を消去します。\n"
                                   "Retro-Go のセーブデータは失われます（先に「セーブデータをPCへバックアップ」を推奨）。"):
            return
        b = Path(self.settings.backup_dir)
        int_name, ext_name = C.backup_names(self.settings.device)
        # Mario --internal-only は bank1 を 256KB 使うため、bank1 も消去してから書き戻す
        cmd = ("gnwmanager erase bank2 -- erase bank1"
               f" -- flash ext {shlex.quote((b / ext_name).as_posix())}"
               f" -- flash bank1 {shlex.quote((b / int_name).as_posix())}"
               " -- start bank1")
        device = self.settings.device

        def forget(ok: bool) -> None:
            if ok:
                self.settings.last_written.pop(device, None)
                self.settings.save()
                self.refresh_builds()
        self.run_steps("純正に戻す", [("純正ファームを書き込み", self.sh(cmd, C.ROOT))], on_done=forget)


def main() -> None:
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        # タスクバーに python ではなくこのアプリのアイコンを出す
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("gnwtool.modder")
    except (AttributeError, OSError):
        pass
    app = App()
    icon = Path(__file__).parent / "assets" / "app.ico"
    if icon.exists():
        try:
            app.iconbitmap(default=str(icon))
        except tk.TclError:
            pass
    app.mainloop()
