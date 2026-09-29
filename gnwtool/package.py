"""ビルド結果を1ファイル (.gnw) にまとめて保存し、後から検証して書き込む.

.gnw は zip で、中身は次の通り:
  manifest.json            機種・書き込み位置・ROM一覧・各ファイルの SHA256
  stock/internal.bin       ② 内部 Bank1 (パッチ済み純正ファーム)
  stock/external.bin       ① 外部フラッシュ先頭 (パッチ済み純正データ。Mario --internal-only では無し)
  retrogo/intflash.bin     ③ 内部 Bank2 (Retro-Go 本体・ROM一覧)
  retrogo/extflash.bin     ④ 外部フラッシュ (エミュレータ・ROM・カバー)
  retrogo/gw_retro_go.elf  セーブデータの位置を調べるためのシンボル情報

③④ は同じビルドから切り出した組でしか動かないため、必ず同じファイルに入れて扱う。
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from . import config as C
from . import toolchain as T

BUILDS = C.ROOT / "builds"
SAVES = C.ROOT / "saves"
FORMAT_VERSION = 1
EXT_BASE = 0x9000_0000

STOCK_INT, STOCK_EXT = "stock/internal.bin", "stock/external.bin"
RG_INT, RG_EXT, RG_ELF = "retrogo/intflash.bin", "retrogo/extflash.bin", "retrogo/gw_retro_go.elf"

# retro-go のROM配列名 -> セーブ領域シンボルの接頭辞 (scripts/saves_backup.sh の対象 + col/sg)
SAVE_ARRAYS = {
    "gb": "GB", "gg": "GG", "gw": "GW", "nes": "NES", "pce": "PCE", "sms": "SMS", "msx": "MSX",
    "wsv": "WSV", "md": "MD", "a7800": "A7800", "amstrad": "AMSTRAD", "zelda3": "ZELDA3",
    "smw": "SMW", "tama": "TAMA", "col": "COL", "sg": "SG1000",
}

Log = Callable[[str], None]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_head(repo: Path) -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=repo, capture_output=True, text=True,
                              creationflags=T.NO_WINDOW).stdout.strip()
    except OSError:
        return ""


# --------------------------------------------------------------------------
# 作成
# --------------------------------------------------------------------------
def create(settings: C.Settings, stock: bool, retrogo: bool, log: Log) -> Path:
    files: dict[str, Path] = {}
    if stock:
        b = C.PATCH_REPO / "build"
        files[STOCK_INT] = b / "internal_flash_patched.bin"
        ext = b / "external_flash_patched.bin"
        if ext.exists() and ext.stat().st_size > 0:
            files[STOCK_EXT] = ext
    if retrogo:
        b = C.RETROGO_REPO / "build"
        files[RG_INT] = b / "gw_retro_go_intflash.bin"
        files[RG_EXT] = b / "gw_retro_go_extflash.bin"
        files[RG_ELF] = b / "gw_retro_go.elf"
    missing = [str(p) for p in files.values() if not p.exists()]
    if missing:
        raise RuntimeError("ビルド結果が見つかりません: " + ", ".join(missing))

    size, offset = settings.extflash_layout()
    roms = []
    if retrogo:
        # ④の見積もりと同じ判定 (.md はメガドライブの ROM。チートのファイル・カバー画像・派生ファイルは除く)
        from .capacity import Estimator
        roms = [{"system": folder, "file": p.name, "size": p.stat().st_size}
                for folder, p in Estimator().scan(C.RETROGO_REPO / "roms")]
    games = sum(1 for r in roms if r["system"] not in ("nes_bios", "msx_bios"))
    manifest = {
        "format": FORMAT_VERSION,
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "device": settings.device,
        "device_name": settings.dev["name"],
        "flash_mb": settings.flash_mb,
        "stock": {
            "patch_params": settings.patch_params(),
            "uses_ext_bytes": files[STOCK_EXT].stat().st_size if STOCK_EXT in files else 0,
        } if stock else None,
        "retrogo": {
            "intflash_address": 0x0810_0000,
            "extflash_offset": offset,
            "extflash_size": size,
            "make_vars": settings.retrogo_vars(),
            "codepage": settings.codepage,
            "coverflow": settings.coverflow,
        } if retrogo else None,
        "roms": roms,
        "repos": {"patch": _git_head(C.PATCH_REPO) if stock else "",
                  "retrogo": _git_head(C.RETROGO_REPO) if retrogo else ""},
        "files": {name: {"sha256": _sha256(p), "size": p.stat().st_size} for name, p in files.items()},
    }
    BUILDS.mkdir(exist_ok=True)
    parts = "+".join(n for n, on in (("純正", stock), ("RetroGo", retrogo)) if on)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    name = f"{stamp}_{settings.device}_{parts}" + (f"_{games}本" if retrogo else "") + ".gnw"
    out = BUILDS / name
    tmp = out.with_suffix(".tmp")
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for arc, p in files.items():
            z.write(p, arc)
    tmp.replace(out)
    log(f"ビルドを保存しました: builds/{out.name} ({out.stat().st_size / 1024 / 1024:.1f} MB)")
    return out


# --------------------------------------------------------------------------
# 読み込み・検証
# --------------------------------------------------------------------------
def read_manifest(path: Path) -> dict:
    with zipfile.ZipFile(path) as z:
        return json.loads(z.read("manifest.json").decode("utf-8"))


def list_packages() -> list[tuple[Path, dict]]:
    out = []
    if BUILDS.is_dir():
        for p in sorted(BUILDS.glob("*.gnw"), reverse=True):
            try:
                out.append((p, read_manifest(p)))
            except (OSError, KeyError, ValueError, zipfile.BadZipFile):
                continue
    return out


def extract(path: Path, dest: Path) -> dict:
    """展開して SHA256 を照合する。壊れていれば例外."""
    with zipfile.ZipFile(path) as z:
        m = json.loads(z.read("manifest.json").decode("utf-8"))
        z.extractall(dest)
    for name, info in m["files"].items():
        f = dest / name
        if not f.exists() or _sha256(f) != info["sha256"]:
            raise RuntimeError(f"{path.name} の {name} が壊れています (SHA256 不一致)")
    return m


@dataclass
class Check:
    errors: list[str]
    warnings: list[str]


def check(m: dict, settings: C.Settings, stock: bool, retrogo: bool) -> Check:
    """保存ビルドを今の本体設定に書いてよいか確認する."""
    err: list[str] = []
    warn: list[str] = []
    if m.get("format", 0) > FORMAT_VERSION:
        err.append("新しいバージョンのツールで作られたファイルです")
    if m["device"] != settings.device:
        err.append(f"このビルドは{m['device_name']}版用です（選択中の本体: {settings.dev['name']}版）")
    if stock and not m.get("stock"):
        err.append("このビルドには純正ファームが含まれていません")
    if retrogo and not m.get("retrogo"):
        err.append("このビルドには Retro-Go が含まれていません")
    if retrogo and m.get("retrogo"):
        rg = m["retrogo"]
        size, offset = settings.extflash_layout()
        if rg["extflash_offset"] != offset:
            err.append(f"外部フラッシュの書き込み位置が違います（ビルド: {rg['extflash_offset'] // 1024}KB目から / "
                       f"今の構成: {offset // 1024}KB目から）。純正側のデータを壊すおそれがあります")
        chip = settings.flash_mb * 1024 * 1024
        if rg["extflash_offset"] + rg["extflash_size"] > chip:
            err.append(f"このビルドは外部フラッシュ {m['flash_mb']}MB 用で、今の構成 ({settings.flash_mb}MB) に収まりません")
        elif rg["extflash_size"] != size:
            warn.append(f"ビルド時の外部フラッシュ構成 ({m['flash_mb']}MB) が今の構成と違います（収まるので書き込みは可能です）")
    if stock and m.get("stock") and m["stock"]["patch_params"] != settings.patch_params():
        warn.append(f"純正パッチのオプションが今の設定と違います（ビルド: {m['stock']['patch_params']}）")
    if stock and not retrogo and m.get("stock"):
        # 純正だけ書く場合、今の本体の Retro-Go 領域と重ならないこと
        used = m["stock"]["uses_ext_bytes"]
        _, offset = settings.extflash_layout()
        if used > offset:
            err.append("純正データが今の Retro-Go 領域と重なります")
    return Check(err, warn)


def describe(m: dict) -> str:
    parts = []
    if m.get("stock"):
        parts.append("純正")
    if m.get("retrogo"):
        games = sum(1 for r in m.get("roms", []) if not r["system"].endswith("_bios"))  # BIOS は数えない
        parts.append(f"Retro-Go（ゲーム {games} 本）")
    return " + ".join(parts)


# --------------------------------------------------------------------------
# 書き込み
# --------------------------------------------------------------------------
def flash_command(dest: Path, m: dict, stock: bool, retrogo: bool) -> str:
    """1回の gnwmanager 接続で選んだ領域をまとめて書くコマンド."""
    q = lambda p: "'" + p.as_posix().replace("'", "'\\''") + "'"  # noqa: E731
    cmds = []
    if stock:
        if STOCK_EXT in m["files"]:
            cmds.append(f"flash ext {q(dest / STOCK_EXT)}")
        cmds.append(f"flash bank1 {q(dest / STOCK_INT)}")
    if retrogo:
        rg = m["retrogo"]
        cmds.append(f"flash 0x{rg['intflash_address']:08x} {q(dest / RG_INT)}")
        cmds.append(f"flash ext {q(dest / RG_EXT)} --offset={rg['extflash_offset']}")
        cmds.append(f"start 0x{rg['intflash_address']:08x}")
    else:
        cmds.append("start bank1")
    return "gnwmanager " + " -- ".join(cmds)


def reset_dbgmcu_command() -> str:
    """retro-go の reset_dbgmcu と同じ (スリープ中にデバッグ用クロックを止める)."""
    cfg = (C.RETROGO_REPO / "scripts" / "interface_stlink.cfg").as_posix()
    return f"openocd -f '{cfg}' -c 'init; reset halt; mww 0x5C001004 0x00000000; resume; exit;'"


# --------------------------------------------------------------------------
# セーブデータ
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class SaveSlot:
    emu: str
    index: int
    name: str
    address: int   # 絶対アドレス (0x9xxxxxxx)
    size: int

    @property
    def filename(self) -> str:
        safe = re.sub(r'[\\/:*?"<>|]', "_", self.name) or f"rom{self.index}"
        return f"{self.emu}/{safe}.save"


def save_slots(elf: Path) -> list[SaveSlot]:
    """ELF から各ROMのセーブ位置を読む (scripts/saves_backup.sh と同じ情報)."""
    gdb = "arm-none-eabi-gdb"
    env = T.build_env()

    def run(exprs: list[str]) -> list[str]:
        args = [gdb, str(elf), "--batch", "-q"]
        for e in exprs:
            args += ["-ex", e]
        r = subprocess.run(args, capture_output=True, env=env, creationflags=T.NO_WINDOW)
        # 表示名は CODEPAGE=932 なら Shift-JIS のバイト列のまま出てくる (UTF-8 で読むと別の ROM と同じ名前に化ける)
        return r.stdout.decode("cp932", errors="replace").splitlines()

    counts: dict[str, int] = {}
    for line in run([f'printf "N|{a}|%d\\n", sizeof({a}_roms)/sizeof({a}_roms[0])' for a in SAVE_ARRAYS]):
        parts = line.split("|")
        if len(parts) == 3 and parts[0] == "N":
            counts[parts[1]] = int(parts[2])
    exprs = [f'printf "S|{a}|{i}|0x%08x|%d|%s\\n", {a}_roms[{i}].save_address, {a}_roms[{i}].save_size, {a}_roms[{i}].name'
             for a, n in counts.items() for i in range(n)]
    slots = []
    for line in run(exprs) if exprs else []:
        parts = line.split("|", 5)
        if len(parts) == 6 and parts[0] == "S":
            addr, size = int(parts[3], 16), int(parts[4])
            if size > 0 and addr >= EXT_BASE:
                slots.append(SaveSlot(parts[1], int(parts[2]), parts[5], addr, size))
    return slots


def same_save_layout(a: list[SaveSlot], b: list[SaveSlot]) -> bool:
    key = lambda s: (s.emu, s.name, s.address, s.size)  # noqa: E731
    return sorted(map(key, a)) == sorted(map(key, b))


# Windows のコマンドラインは 32,767 文字まで。セーブ 200 件以上を 1 つにつなぐと超えて
# [WinError 206] になるので、この長さで分けて複数回の接続にする
MAX_CMDLINE = 8000


def _chain(cmds: list[str]) -> list[str]:
    """gnwmanager のサブコマンドを "--" でつなぎ、MAX_CMDLINE を超えないように分ける."""
    out, cur = [], []
    for c in cmds:
        if cur and len("gnwmanager " + " -- ".join(cur + [c])) > MAX_CMDLINE:
            out.append("gnwmanager " + " -- ".join(cur))
            cur = []
        cur.append(c)
    if cur:
        out.append("gnwmanager " + " -- ".join(cur))
    return out


def backup_commands(slots: list[SaveSlot], outdir: Path) -> list[str]:
    cmds = []
    for s in slots:
        dst = (outdir / s.filename).as_posix().replace("'", "'\\''")
        cmds.append(f"dump 0x{s.address:08x} --dst '{dst}' --size {s.size}")
    return _chain(cmds)


def restore_commands(slots: list[SaveSlot], indir: Path) -> tuple[list[str], list[str]]:
    """ROM名が一致するセーブだけを新しい位置へ書き戻す。戻り値: (コマンドの列, 復元したROM名)."""
    cmds, restored = [], []
    for s in slots:
        f = indir / s.filename
        if f.exists() and f.stat().st_size == s.size:
            src = f.as_posix().replace("'", "'\\''")
            cmds.append(f"flash ext '{src}' --offset={s.address - EXT_BASE}")
            restored.append(f"{s.emu}/{s.name}")
    return _chain(cmds), restored


def elf_of(package: Path, workdir: Path) -> Optional[Path]:
    """パッケージから ELF だけ取り出す."""
    try:
        with zipfile.ZipFile(package) as z:
            if RG_ELF not in z.namelist():
                return None
            z.extract(RG_ELF, workdir)
        return workdir / RG_ELF
    except (OSError, zipfile.BadZipFile):
        return None


def new_workdir() -> Path:
    return Path(tempfile.mkdtemp(prefix="gnwpkg_"))


def remove_workdir(d: Path) -> None:
    shutil.rmtree(d, ignore_errors=True)
