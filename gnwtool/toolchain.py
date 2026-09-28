"""ビルド/書き込みに必要なツールの検出と自動導入."""
from __future__ import annotations

import glob
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Optional

from . import config as C

Log = Callable[[str], None]
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


# --------------------------------------------------------------------------
# 検出
# --------------------------------------------------------------------------
def find_git_root() -> Optional[Path]:
    candidates = [C.GIT_DIR]  # 持ち運び版の PortableGit を優先
    git = shutil.which("git")
    if git:
        candidates.append(Path(git).resolve().parents[1])
    for env in ("ProgramFiles", "ProgramW6432", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if base:
            candidates += [Path(base) / "Git", Path(base) / "Programs" / "Git"]
    for root in candidates:
        if (root / "usr" / "bin" / "bash.exe").exists():
            return root
    return None


def _gcc_major(gcc: Path) -> Optional[int]:
    try:
        out = subprocess.run([str(gcc), "-dumpversion"], capture_output=True, text=True,
                             timeout=20, creationflags=NO_WINDOW).stdout.strip()
        return int(out.split(".")[0])
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def find_gcc_bin() -> Optional[Path]:
    """GCC 10〜14 の arm-none-eabi-gcc があるbinディレクトリ。ツール同梱版を優先."""
    candidates = [Path(p) for p in glob.glob(str(C.GCC_DIR / "*" / "bin" / "arm-none-eabi-gcc.exe"))]
    found = shutil.which("arm-none-eabi-gcc")
    if found:
        candidates.append(Path(found))
    for pf in ("ProgramFiles(x86)", "ProgramFiles"):
        base = os.environ.get(pf)
        if base:
            candidates += [Path(p) for p in glob.glob(
                str(Path(base) / "Arm GNU Toolchain arm-none-eabi" / "*" / "bin" / "arm-none-eabi-gcc.exe"))]
            candidates += [Path(p) for p in glob.glob(
                str(Path(base) / "GNU Arm Embedded Toolchain" / "*" / "bin" / "arm-none-eabi-gcc.exe"))]
    for gcc in candidates:
        major = _gcc_major(gcc)
        if major is not None and C.GCC_MIN <= major <= C.GCC_MAX:
            return gcc.parent
    return None


def find_openocd_bin() -> Optional[Path]:
    hits = glob.glob(str(C.OPENOCD_DIR / "*" / "bin" / "openocd.exe"))
    return Path(hits[0]).parent if hits else None


def make_ok() -> bool:
    return (C.SHIM_BIN / "make.exe").exists()


def venv_ok() -> bool:
    if not C.VENV_PY.exists():
        return False
    r = subprocess.run([str(C.VENV_PY), "-c", "import gnwmanager, keystone, elftools, lz4, zstandard"],
                       capture_output=True, creationflags=NO_WINDOW)
    return r.returncode == 0


def repos_ok() -> bool:
    return (C.PATCH_REPO / "Makefile").exists() and (C.RETROGO_REPO / "Makefile").exists() \
        and (C.RETROGO_REPO / "retro-go-stm32" / ".git").exists()


def status() -> dict[str, tuple[bool, str]]:
    git = find_git_root()
    gcc = find_gcc_bin()
    ocd = find_openocd_bin()
    return {
        "git": (git is not None, str(git) if git else "未検出: Git for Windows をインストールしてください"),
        "repos": (repos_ok(), str(C.WORKSPACE) if repos_ok() else "未取得"),
        "venv": (venv_ok(), str(C.VENV) if venv_ok() else "未構築"),
        "make": (make_ok(), str(C.SHIM_BIN / "make.exe") if make_ok() else "未導入"),
        "gcc": (gcc is not None, str(gcc) if gcc else "未導入 (GCC 10〜14 が必要)"),
        "openocd": (ocd is not None, str(ocd) if ocd else "未導入"),
    }


# --------------------------------------------------------------------------
# 実行環境
# --------------------------------------------------------------------------
def build_env() -> dict[str, str]:
    env = os.environ.copy()
    git = find_git_root()
    paths = [str(C.SHIM_BIN), str(C.VENV_SCRIPTS)] + ([str(C.PORTABLE_PY)] if C.PORTABLE else [])
    gcc = find_gcc_bin()
    if gcc:
        paths.append(str(gcc))
    ocd = find_openocd_bin()
    if ocd:
        paths.append(str(ocd))
    if git:
        paths += [str(git / "usr" / "bin"), str(git / "mingw64" / "bin"), str(git / "cmd")]
    env["PATH"] = os.pathsep.join(paths + [env.get("PATH", "")])
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["LANG"] = "C.UTF-8"
    env.pop("VIRTUAL_ENV", None)
    if C.PORTABLE:  # その PC のユーザー用 site-packages を混ぜない
        env["PYTHONNOUSERSITE"] = "1"
    return env


def bash_exe() -> Path:
    git = find_git_root()
    if not git:
        raise RuntimeError("Git for Windows が見つかりません。https://git-scm.com/download/win からインストールしてください。")
    return git / "usr" / "bin" / "bash.exe"


# --------------------------------------------------------------------------
# 導入処理 (ワーカースレッドから呼ばれる)
# --------------------------------------------------------------------------
def run_cmd(args: list[str], log: Log, cwd: Optional[Path] = None, check: bool = True, proc_hook=None) -> int:
    log("$ " + " ".join(args))
    p = subprocess.Popen(args, cwd=cwd, env=build_env(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, creationflags=NO_WINDOW)
    if proc_hook:
        proc_hook(p)
    assert p.stdout
    for raw in p.stdout:
        log(raw.decode("utf-8", errors="replace").rstrip("\r\n"))
    rc = p.wait()
    if check and rc != 0:
        raise RuntimeError(f"コマンドが失敗しました (終了コード {rc})")
    return rc


def download(url: str, dest: Path, log: Log) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    log(f"ダウンロード: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "gnwtool"})
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done, last = 0, -10
        while chunk := r.read(1 << 20):
            f.write(chunk)
            done += len(chunk)
            if total:
                pct = done * 100 // total
                if pct >= last + 10:
                    log(f"  {pct}% ({done // (1 << 20)}MB / {total // (1 << 20)}MB)")
                    last = pct
    tmp.replace(dest)
    return dest


def _system_python() -> str:
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":
        cand = exe.with_name("python.exe")
        if cand.exists():
            return str(cand)
    return str(exe)


def setup_repos(log: Log, proc_hook=None) -> None:
    C.WORKSPACE.mkdir(parents=True, exist_ok=True)
    if not (C.PATCH_REPO / ".git").exists():
        run_cmd(["git", "clone", "--depth", "1", C.PATCH_URL, str(C.PATCH_REPO)], log, proc_hook=proc_hook)
    if not (C.RETROGO_REPO / ".git").exists():
        run_cmd(["git", "clone", "--depth", "1", "--recurse-submodules", "--shallow-submodules",
                 C.RETROGO_URL, str(C.RETROGO_REPO)], log, proc_hook=proc_hook)
    else:
        run_cmd(["git", "submodule", "update", "--init", "--depth", "1"], log, cwd=C.RETROGO_REPO,
                proc_hook=proc_hook)


def update_repos(log: Log, proc_hook=None) -> None:
    for repo in (C.PATCH_REPO, C.RETROGO_REPO):
        # ビルドで更新される追跡ファイル (patches/keystone_cache.json 等) を戻してから pull する
        run_cmd(["git", "checkout", "--", "."], log, cwd=repo, proc_hook=proc_hook)
        run_cmd(["git", "pull", "--ff-only"], log, cwd=repo, proc_hook=proc_hook)
    run_cmd(["git", "submodule", "update", "--init", "--depth", "1"], log, cwd=C.RETROGO_REPO, proc_hook=proc_hook)


def setup_venv(log: Log, proc_hook=None) -> None:
    if not C.PORTABLE and not C.VENV_PY.exists():
        run_cmd([_system_python(), "-m", "venv", str(C.VENV)], log, proc_hook=proc_hook)
    run_cmd([str(C.VENV_PY), "-m", "pip", "install", "--upgrade", "pip"], log, proc_hook=proc_hook)
    run_cmd([str(C.VENV_PY), "-m", "pip", "install",
             "-r", str(C.PATCH_REPO / "requirements.txt"),
             "-r", str(C.RETROGO_REPO / "requirements.txt"),
             "gnwmanager", "zstandard"], log, proc_hook=proc_hook)


def write_shims() -> None:
    """Makefile が期待する python3 / wget と、gnwmanager を用意する.

    パスは tools/bin からの相対にする (フォルダごと移動しても使えるように)。gnwmanager は
    pip が作る Scripts/gnwmanager.exe が python の絶対パスを埋め込んでいて移動すると動かないため、
    python -m gnwmanager で呼ぶ.
    """
    C.SHIM_BIN.mkdir(parents=True, exist_ok=True)
    py = '"$(dirname "$0")/../' + C.VENV_PY.relative_to(C.TOOLS).as_posix() + '"'
    (C.SHIM_BIN / "python3").write_bytes(f'#!/bin/sh\nexec {py} "$@"\n'.encode())
    (C.SHIM_BIN / "gnwmanager").write_bytes(f'#!/bin/sh\nexec {py} -m gnwmanager "$@"\n'.encode())
    (C.SHIM_BIN / "wget").write_bytes(
        b'#!/bin/sh\n'
        b'# Minimal wget replacement (curl based) supporting: wget [-q] URL [-P DIR] [-O FILE]\n'
        b'dir=.; out=; url=\n'
        b'while [ $# -gt 0 ]; do\n'
        b'  case "$1" in\n'
        b'    -q) ;;\n'
        b'    -P) dir="$2"; shift ;;\n'
        b'    -O) out="$2"; shift ;;\n'
        b'    *) url="$1" ;;\n'
        b'  esac\n'
        b'  shift\n'
        b'done\n'
        b'[ -z "$out" ] && out="$dir/$(basename "$url")"\n'
        b'mkdir -p "$(dirname "$out")"\n'
        b'exec curl -fsSL --retry 3 -o "$out" "$url"\n')


def setup_make(log: Log, proc_hook=None) -> None:
    write_shims()
    if make_ok():
        return
    pkg = download(C.MAKE_PKG_URL, C.TOOLS / "downloads" / "make.pkg.tar.zst", log)
    log("make を展開中…")
    script = (
        "import sys, tarfile, zstandard, io\n"
        "data = zstandard.ZstdDecompressor().stream_reader(open(sys.argv[1], 'rb'))\n"
        "with tarfile.open(fileobj=io.BytesIO(data.read()), mode='r:') as t:\n"
        "    m = t.getmember('usr/bin/make.exe')\n"
        "    open(sys.argv[2], 'wb').write(t.extractfile(m).read())\n"
    )
    run_cmd([str(C.VENV_PY), "-c", script, str(pkg), str(C.SHIM_BIN / "make.exe")], log, proc_hook=proc_hook)


def _download_and_unzip(url: str, target: Path, log: Log) -> None:
    z = download(url, C.TOOLS / "downloads" / url.rsplit("/", 1)[-1], log)
    log(f"展開中: {z.name}")
    if target.exists():
        shutil.rmtree(target)
    with zipfile.ZipFile(z) as zf:
        zf.extractall(target)


def setup_gcc(log: Log, proc_hook=None) -> None:
    if find_gcc_bin():
        log(f"ARM GCC: {find_gcc_bin()} を使用します")
        return
    _download_and_unzip(C.GCC_URL, C.GCC_DIR, log)


def setup_openocd(log: Log, proc_hook=None) -> None:
    if find_openocd_bin():
        return
    _download_and_unzip(C.OPENOCD_URL, C.OPENOCD_DIR, log)


# --------------------------------------------------------------------------
# バックアップ検証
# --------------------------------------------------------------------------
def verify_backups(backup_dir: Path, device: str) -> list[tuple[str, bool, str]]:
    dev = C.DEVICES[device]
    int_name, ext_name = C.backup_names(device)
    results = []
    for name, size, is_int in ((int_name, C.INT_SIZE, True), (ext_name, dev["ext_size"], False)):
        p = backup_dir / name
        if not p.exists():
            results.append((name, False, "ファイルがありません"))
            continue
        if p.stat().st_size != size:
            results.append((name, False, f"サイズ不正 ({p.stat().st_size} bytes, 期待値 {size})"))
            continue
        data = p.read_bytes()
        if is_int:
            ok = hashlib.sha1(data).hexdigest() == dev["int_sha1"]
        else:
            s, e = dev["ext_hash_range"]
            ok = hashlib.sha1(data[s:e]).hexdigest() == dev["ext_sha1"]
        results.append((name, ok, "純正ファームと一致" if ok else
                        f"SHA1が純正と一致しません（{dev['name']}以外/破損の可能性）"))
    return results


# --------------------------------------------------------------------------
# ROM フォルダ
# --------------------------------------------------------------------------
ROMS_README = """ここに機種ごとのフォルダへROMイメージを入れてください。
ツールが容量を自動計算し、ビルド時に retro-go へ同期します。

{lines}

・ご自身が所有するソフトから吸い出したROMのみを使用してください。
・カバー画像 (パッケージ画像) は ROM と同じフォルダに同じファイル名で置きます。
  例: nes\Zelda.nes → nes\Zelda.png  (png / jpg / jpeg / bmp)
  ビルド時に 128×96 (4:3) へ引き伸ばして JPEG に変換されるため、4:3 の画像がきれいに表示されます。
  使うには ③構成で「カバーアート表示」を有効にしてください。
・ファイル名末尾を _no_save にするとその ROM のセーブ領域を確保しません。
"""


def cheat_files(folder: str) -> list[Path]:
    d = C.CHEATS / folder
    if not d.is_dir():
        return []
    return [p for p in d.iterdir() if p.is_file() and p.suffix.lower() in C.CHEAT_SUFFIXES]


def cheat_count(rom: Path) -> int:
    """ROM に対応するチートの件数 (roms 側 → cheat_code 側の順に探す)."""
    from .capacity import rom_stem
    stem = rom_stem(rom)
    for d in (rom.parent, C.CHEATS / rom.parent.name):
        for suf in C.CHEAT_SUFFIXES:
            f = d / (stem + suf)
            if f.exists():
                try:
                    lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
                except OSError:
                    return 0
                if suf == ".mcf":
                    return sum(1 for ln in lines if ln.strip())
                return min(16, sum(1 for ln in lines if ln.split(",", 1)[0].strip()))
    return 0


# ---- 表示名 (roms/<機種>.json) ----------------------------------------------
# retro-go の romdef 形式 {"<ROM名(拡張子なし)>": {"name": "<表示名>"}}。parse_roms.py が roms/<機種>.json を読む。
# ファイル名は英数字でないとビルドが失敗するが、表示名は CODEPAGE=932 なら日本語にできる。
def names_file(folder: str) -> Path:
    return C.ROMS / f"{folder}.json"


def load_names(folder: str) -> dict[str, str]:
    try:
        data = json.loads(names_file(folder).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v["name"] for k, v in data.items() if isinstance(v, dict) and v.get("name")}


def save_names(folder: str, names: dict[str, str]) -> None:
    f = names_file(folder)
    names = {k: v for k, v in names.items() if v and v != k}
    if not names:
        f.unlink(missing_ok=True)
        return
    f.write_text(json.dumps({k: {"name": v} for k, v in sorted(names.items())}, ensure_ascii=False, indent=1),
                 encoding="utf-8")


def fix_non_ascii_names(log: Log) -> int:
    """英数字以外を含む ROM のファイル名を付け替え、元の名前は表示名として残す。関連ファイルも一緒に."""
    import re
    import zlib
    from .capacity import ALL_COVER_SUFFIXES, rom_stem
    fixed = 0
    for folder, _, _ in C.ROM_SYSTEMS:
        d = C.ROMS / folder
        if not d.is_dir():
            continue
        names = load_names(folder)
        for p in sorted(d.iterdir()):
            if not p.is_file() or p.name.isascii() or p.suffix.lower() in ALL_COVER_SUFFIXES + C.CHEAT_SUFFIXES:
                continue
            stem = rom_stem(p)
            ascii_part = re.sub(r"[^A-Za-z0-9]+", "_", stem.encode("ascii", "ignore").decode()).strip("_")
            new_stem = f"{ascii_part or 'rom'}_{zlib.crc32(stem.encode('utf-8')) & 0xFFFFFFFF:08X}"
            related = [q for q in d.iterdir() if q.is_file() and rom_stem(q) == stem]
            related += [q for q in (d / ".cover_originals").glob(f"{stem}.*")] if (d / ".cover_originals").is_dir() else []
            related += [q for q in (C.CHEATS / folder).glob(f"{stem}.*")] if (C.CHEATS / folder).is_dir() else []
            for q in related:
                q.rename(q.with_name(new_stem + q.name[len(stem):]))
                log(f"名前を変更: {folder}/{q.name} → {new_stem + q.name[len(stem):]}")
            names[new_stem] = names.pop(stem, stem)
            fixed += 1
        save_names(folder, names)
    return fixed


def ensure_roms_dirs() -> None:
    for folder, _, _ in C.ROM_SYSTEMS:
        (C.ROMS / folder).mkdir(parents=True, exist_ok=True)
    readme = C.ROMS / "README.txt"
    lines = "\n".join(f"  {folder:<9} {name}  ({exts})" for folder, name, exts in C.ROM_SYSTEMS)
    text = ROMS_README.format(lines=lines)
    try:
        if readme.read_text(encoding="utf-8") == text:
            return
    except OSError:
        pass
    readme.write_text(text, encoding="utf-8")


# retro-go 側で保持するファイル (リポジトリ管理下のもの)
_KEEP = {".keep", "readme.md", "msxromdb.xml"}
_DERIVED = (".lzma", ".cdk")


def _force_unlink(p: Path) -> None:
    try:
        p.unlink()
    except PermissionError:
        os.chmod(p, stat.S_IREAD | stat.S_IWRITE)
        p.unlink()


def sync_roms(log: Log, proc_hook=None) -> None:
    """プロジェクトの roms/ を retro-go/roms/ へミラーする.

    retro-go は ROM の隣に .lzma 等の圧縮済みファイルを作り、存在すれば再圧縮しないため、
    元ファイルが変わった/消えた場合は派生ファイルも削除する。
    """
    ensure_roms_dirs()
    copied = removed = 0
    for folder, _, _ in C.ROM_SYSTEMS:
        src_dir, dst_dir = C.ROMS / folder, C.RETROGO_REPO / "roms" / folder
        dst_dir.mkdir(parents=True, exist_ok=True)
        src = {p.name: p for p in src_dir.iterdir() if p.is_file() and p.name.lower() not in _KEEP}
        # cheat_code/<機種>/ のチート定義も ROM の隣に置く (roms 側に同名があればそちらを優先)
        for p in cheat_files(folder):
            src.setdefault(p.name, p)
        for d in list(dst_dir.iterdir()):
            if not d.is_file() or d.name.lower() in _KEEP or d.name.lower().endswith(".json"):
                continue
            base = d.name
            for suf in _DERIVED:
                if base.lower().endswith(suf):
                    base = base[: -len(suf)]
                    break
            if base.lower().endswith(".dsk.cdk"):
                base = base[:-4]
            s = src.get(base) or src.get(base.rsplit(".", 1)[0] + ".dsk")
            stale = s is None
            if not stale and d.name == s.name:
                st, dt = s.stat(), d.stat()
                stale = st.st_size != dt.st_size or int(st.st_mtime) != int(dt.st_mtime)
            elif not stale:
                stale = s.stat().st_mtime > d.stat().st_mtime
            if stale:
                _force_unlink(d)
                removed += 1
        for name, s in src.items():
            d = dst_dir / name
            if not d.exists():
                shutil.copy2(s, d)
                # 読み取り専用属性まで引き継ぐと、次回の入れ替えで消せなくなる (retro-go も BIOS を書き換える)
                os.chmod(d, stat.S_IREAD | stat.S_IWRITE)
                copied += 1
        # 表示名 (roms/<機種>.json) も同期。無ければ retro-go 側からも消す
        src_names, dst_names = names_file(folder), C.RETROGO_REPO / "roms" / f"{folder}.json"
        if src_names.exists():
            shutil.copy2(src_names, dst_names)
        elif dst_names.exists():
            _force_unlink(dst_names)
    log(f"ROM同期: コピー {copied} 件 / 削除 {removed} 件")
