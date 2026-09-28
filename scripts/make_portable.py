"""持ち運び版を作る: フォルダの中だけで完結し、フォルダごとコピーすれば別の PC でも動く.

使い方:  python scripts\\make_portable.py [出力先]   (既定: このフォルダの隣の game_watch_kai)
  - 画面・ビルド用の Python は、venv の元になっている Python 一式を tools\\python にコピーし、
    venv のパッケージを重ねる (venv は元の Python の場所を覚えていて、移動すると動かないため)
  - Git は PortableGit、ARM GCC は xPack 版を tools\\ に入れる (ダウンロードは tools\\downloads に残して再利用)
  - 起動用の GnW改造ツール.exe は Windows 標準の csc.exe でビルドする (scripts\\portable\\launcher.cs)
  - ROM・純正バックアップ・セーブ・保存ビルド・設定もコピーする (--no-data で省く)
  - PC ごとに要るもの: ST-Link の USB ドライバ (STSW-LINK009) だけ
何度実行してもよい (コピーは差分だけ、ツールは入っていれば飛ばす)。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from gnwtool import config as C  # noqa: E402

GIT_URL = ("https://github.com/git-for-windows/git/releases/download/v2.55.0.windows.5/"
           "PortableGit-2.55.0.5-64-bit.7z.exe")
DOWNLOADS = ROOT / "tools" / "downloads"
CSC = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Microsoft.NET" / "Framework64" / "v4.0.30319" / "csc.exe"
EXE_NAME = "GnW改造ツール.exe"
APP_FILES = ["gnwtool", "scripts", "cheat_code", "README.md", "manual.md", "AGENTS.md"]
DATA = ["roms", "backup_rom", "saves", "builds"]


def log(msg: str) -> None:
    print(msg, flush=True)


def robocopy(src: Path, dst: Path, *extra: str) -> None:
    """src の中身を dst へ (差分だけ)。robocopy の終了コードは 8 未満が成功."""
    r = subprocess.run(["robocopy", str(src), str(dst), "/E", "/NFL", "/NDL", "/NJH", "/NJS", "/NP",
                        "/R:1", "/W:1", *extra])
    if r.returncode >= 8:
        raise RuntimeError(f"コピーに失敗しました: {src} → {dst} (robocopy {r.returncode})")


def download(url: str) -> Path:
    dest = DOWNLOADS / url.rsplit("/", 1)[-1]
    if dest.exists():
        return dest
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    log(f"ダウンロード: {url}")
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "gnwtool"})
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f, 1 << 20)
    tmp.replace(dest)
    return dest


def base_python() -> Path:
    """venv の元になっている Python のフォルダ (pyvenv.cfg の home)."""
    cfg = (C.TOOLS / "venv" / "pyvenv.cfg").read_text(encoding="utf-8")
    home = Path(re.search(r"^home\s*=\s*(.+)$", cfg, re.M).group(1).strip())
    if not (home / "pythonw.exe").exists():
        raise RuntimeError(f"元の Python が見つかりません: {home}")
    return home


def copy_app(dest: Path) -> None:
    log("== ツール本体")
    for name in APP_FILES:
        src = ROOT / name
        if src.is_dir():
            robocopy(src, dest / name, "/XD", "__pycache__")
        else:
            shutil.copy2(src, dest / name)


def copy_data(dest: Path) -> None:
    log("== ROM・純正バックアップ・セーブ・保存ビルド・設定")
    for name in DATA:
        if (ROOT / name).is_dir():
            robocopy(ROOT / name, dest / name)
    if C.SETTINGS_FILE.exists():
        data = json.loads(C.SETTINGS_FILE.read_text(encoding="utf-8"))
        # フォルダ内のパスは相対にする (config.Settings.load() が ROOT を基準に戻す)
        dirs = {}
        for k, v in data.get("backup_dirs", {}).items():
            try:
                dirs[k] = str(Path(v).resolve().relative_to(ROOT))
            except ValueError:
                dirs[k] = v
                log(f"注意: {k} のバックアップの場所がフォルダの外です（コピーしていません）: {v}")
        data["backup_dirs"] = dirs
        (dest / "settings.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def copy_workspace(dest: Path) -> None:
    log("== ソース (workspace)。ビルドの途中生成物 (build) は除く")
    ws = ROOT / "workspace"
    robocopy(ws, dest / "workspace", "/XD", str(ws / "game-and-watch-retro-go" / "build"),
             str(ws / "game-and-watch-patch" / "build"), "__pycache__")


def setup_python(dest: Path) -> Path:
    log("== Python (tools\\python)")
    py_dir = dest / "tools" / "python"
    robocopy(base_python(), py_dir, "/XD", "__pycache__")
    log("  venv のパッケージを重ねる")
    robocopy(C.TOOLS / "venv" / "Lib" / "site-packages", py_dir / "Lib" / "site-packages", "/XD", "__pycache__")
    # venv の Scripts\*.exe は python の絶対パスを埋め込んでいるのでコピーしない (gnwmanager は tools\bin のシムで呼ぶ)
    return py_dir / "python.exe"


def setup_tools(dest: Path) -> None:
    log("== make・OpenOCD・チートの出典キャッシュ")
    for name in ("bin", "openocd", "cache"):
        if (C.TOOLS / name).is_dir():
            robocopy(C.TOOLS / name, dest / "tools" / name)

    git_dir = dest / "tools" / "git"
    if not (git_dir / "usr" / "bin" / "bash.exe").exists():
        log("== Git (PortableGit)")
        sfx = download(GIT_URL)
        subprocess.run([str(sfx), f"-o{git_dir}", "-y"], check=True)

    gcc_dir = dest / "tools" / "arm-gcc"
    if not list(gcc_dir.glob("*/bin/arm-none-eabi-gcc.exe")):
        log("== ARM GCC (xPack)")
        z = download(C.GCC_URL)
        with zipfile.ZipFile(z) as zf:
            zf.extractall(gcc_dir)


def build_launcher(dest: Path) -> None:
    log(f"== 起動用の {EXE_NAME}")
    icon = ROOT / "gnwtool" / "assets" / "app.ico"
    subprocess.run([str(CSC), "/nologo", "/target:winexe", "/optimize+", f"/win32icon:{icon}",
                    f"/out:{dest / EXE_NAME}", str(ROOT / "scripts" / "portable" / "launcher.cs")], check=True)
    # ショートカット作成用 (.bat は cmd が Shift-JIS で読むので cp932・CRLF)
    bat = ("@echo off\r\n"
           "rem デスクトップとこのフォルダに、ショートカット「GnW改造ツール」を作成します\r\n"
           "cd /d \"%~dp0\"\r\n"
           "set PYTHONNOUSERSITE=1\r\n"
           "\"%~dp0tools\\python\\python.exe\" -m gnwtool.shortcut\r\n"
           "if errorlevel 1 pause\r\n")
    (dest / "ショートカット作成.bat").write_bytes(bat.encode("cp932"))
    (dest / "はじめにお読みください.txt").write_text(README, encoding="utf-8-sig")


def finish(dest: Path, py: Path) -> None:
    log("== 仕上げ: シムを作り、持ち運び版の Python でツールを確かめる")
    env = {**os.environ, "PYTHONNOUSERSITE": "1"}
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONPATH", None)
    code = ("from gnwtool import config as C, toolchain as T\n"
            "assert C.PORTABLE, 'tools\\\\python が使われていません'\n"
            "T.write_shims()\n"
            "for k, (ok, detail) in T.status().items():\n"
            "    print(f'  {k:8} {\"OK\" if ok else \"NG\"}  {detail}')\n"
            "import tkinter, PIL; print('  tkinter / Pillow OK', PIL.__version__)\n")
    subprocess.run([str(py), "-c", code], cwd=dest, env=env, check=True)


README = """G&W 改造ツール（持ち運び版）

■ 起動
  「GnW改造ツール.exe」をダブルクリックします。
  デスクトップにショートカットを作るときは「ショートカット作成.bat」を実行します。

■ 別の PC へ移す
  このフォルダをまるごとコピーしてください（中身だけでビルド・書き込みまでできます）。
  Python・Git・ARM GCC・OpenOCD はフォルダの中に入っているので、インストールは不要です。

■ PC ごとに必要なもの
  ST-Link の USB ドライバ（STSW-LINK009）だけは、PC ごとにインストールが必要です。
  ツールの「① 環境セットアップ」にある「STSW-LINK009 のページを開く」から入手できます。

■ 注意
  ・Windows（64bit）専用です。
  ・フォルダの場所は、なるべく短いパス（例: D:\\game_watch_kai）にしてください。
  ・roms・backup_rom・saves・builds には個人のデータが入っています。人に渡すときは注意してください。
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dest", nargs="?", default=str(ROOT.parent / "game_watch_kai"))
    ap.add_argument("--no-data", action="store_true", help="ROM・バックアップ・セーブ・保存ビルド・設定をコピーしない")
    args = ap.parse_args()
    dest = Path(args.dest).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    copy_app(dest)
    if not args.no_data:
        copy_data(dest)
    copy_workspace(dest)
    py = setup_python(dest)
    setup_tools(dest)
    build_launcher(dest)
    finish(dest, py)
    log(f"完了: {dest}")


if __name__ == "__main__":
    main()
