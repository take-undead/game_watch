"""roms フォルダの内容から Retro-Go の外部フラッシュ使用量を見積もる.

retro-go (sylverb/msx_wsv_genesis) の parse_roms.py / リンカスクリプトの挙動を再現している。
数値はダミーROMを使った実ビルドの結果と照合済み (ROMデータ・セーブ領域はバイト単位で一致)。
"""
from __future__ import annotations

import hashlib
import json
import lzma
import re
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import config as C

ALIGN = 4096

# parse_roms.py の SAVE_SIZES (gb/nes は個別計算)
SAVE_SIZES = {
    "nes": 24 * 1024, "sms": 60 * 1024, "gg": 60 * 1024, "col": 60 * 1024, "sg": 60 * 1024,
    "pce": 76 * 1024, "msx": 272 * 1024, "gw": 4 * 1024, "wsv": 28 * 1024, "md": 144 * 1024,
    "a7800": 36 * 1024, "amstrad": 132 * 1024, "tama": 8 * 1024,
}

# 圧縮対象と、それ以上だと圧縮をスキップする上限サイズ (parse_roms.py の MAX_COMPRESSED_*)
COMPRESS_LIMIT = {
    "nes": 0x00080010, "pce": 0x00049000, "msx": 136 * 1024, "wsv": 0x00080000,
    "a7800": 131200, "amstrad": None, "gb": None,
}

# 機種ごとのエミュレータコード (外部フラッシュ上の overlay セクション, bytes)。実ビルドで計測。
# amstrad は計測できていないため推定値 (msx は実ROMでのビルドで計測済み)。
EMU_CODE = {
    "nes": 62144, "gb": 48088, "sms": 66008, "gg": 66008, "col": 66008, "sg": 66008,
    "pce": 37924, "wsv": 23128, "md": 564616, "a7800": 91432, "gw": 21592,
    "msx": 176448, "amstrad": 200 * 1024, "tama": 34968,
}
EMU_CODE_ESTIMATED = {"amstrad"}
# fceumm は入れた ROM が使うマッパーのコードだけを組み込む。0 番以外 1 種類あたりの平均 (実ビルド: 10 種で +11096)
NES_MAPPER_CODE = 1110
# 1つのoverlayを共有する機種
EMU_GROUP = {"sms": "sms", "gg": "sms", "col": "sms", "sg": "sms"}

# ROMデータの前に置かれる固定データ (フォント + 機種別のエミュレータ用データ)。
# ROMデータはその後の 4KB 境界から始まる。機種ごとに1本ずつ入れた実ビルドで計測。
FIXED_COMMON = 4  # extflash_magic_sign
# NES: パレット等 / SMS系: ColecoVision BIOS 等 / MSX: YJK 色変換表 (msxYjkColor)
FIXED_EMU_DATA = {"nes": 40252, "sms": 8192, "msx": 262144}
FONT_DATA = {"1252": 0, "932": 212816}  # 日本語フォント (CODEPAGE=932)
CONFIG_FLASH = 4096
SCREENSHOT_FLASH = ((320 * 240 * 2 + 4095) // 4096) * 4096
SAFETY_MARGIN = 64 * 1024

# ROM ではないファイル (変換済みデータ・カバー画像・チート定義 .ggcodes/.pceplus/.mcf など ROM の付属ファイル)
CHEAT_SUFFIX = {".ggcodes", ".pceplus", ".mcf"}
SKIP_SUFFIX = {".json", ".txt", ".xml", ".lzma", ".cdk", ".keep", ".img", ".png", ".jpg", ".jpeg", ".bmp"} | CHEAT_SUFFIX
# parse_roms.py が探す順番 (ROM と同じフォルダ・同じファイル名)
COVER_SUFFIXES = (".png", ".jpg", ".jpeg", ".bmp")
# .img は parse_roms.py が作る変換済み JPEG。元画像が無ければそのまま使われる
IMG_SUFFIX = ".img"
ALL_COVER_SUFFIXES = COVER_SUFFIXES + (IMG_SUFFIX,)
IMAGE_SUFFIX = set(ALL_COVER_SUFFIXES)
# parse_roms.py の parse_msx_bios_files() と同じ照合。1つでも合わないと MSX は使えない
MSX_BIOS = {
    "MSX.rom": ("MSX1 BIOS / BASIC", {"e998f0c441f4f1800ef44e42cd1659150206cf79"}),
    "MSX2.rom": ("MSX2 BIOS / BASIC", {"6103b39f1e38d1aa2d84b1c3219c44f1abb5436e"}),
    "MSX2EXT.rom": ("MSX2 拡張ROM", {"5c1f9c7fb655e43d38e5dd1fcc6b942b2ff68b02"}),
    "MSX2P.rom": ("MSX2+ BIOS / BASIC", {"e90f80a61d94c617850c415e12ad70ac41e66bb7"}),
    "MSX2PEXT.rom": ("MSX2+ 拡張ROM", {"fe0254cbfc11405b79e7c86c7769bd6322b04995"}),
    "MSX2PMUS.rom": ("MSX-MUSIC", {"6354ccc5c100b1c558c9395fa8c00784d2e9b0a3"}),
    # 以前の retro-go がパッチを当てた版も、ビルド時に元へ戻されるので可
    "PANASONICDISK.rom": ("ディスクROM", {"7ed7c55e0359737ac5e68d38cb6903f9e5d7c2b6",
                                        "b9bce28fb74223ea902f82ebd107279624cf2aba"}),
}
MSX_DISK_PATCHED = "PANASONICDISK_.rom"  # ビルド時に自動生成される (2台目のFDDを無効化した版)
FDS_BIOS = "disksys.rom"
FDS_BIOS_SIZE = 8192
COVER_DEFAULT = (128, 96)
EXTS = {folder: {e for e in exts.split() if e.startswith(".")} for folder, _, exts in C.ROM_SYSTEMS}


def align(n: int) -> int:
    return (n + ALIGN - 1) // ALIGN * ALIGN


def _lzma(data: bytes) -> int:
    out = lzma.compress(data, format=lzma.FORMAT_ALONE,
                        filters=[{"id": lzma.FILTER_LZMA1, "preset": 6, "dict_size": 16 * 1024}])
    return len(out) - 13


def stored_size(folder: str, data: bytes) -> tuple[int, bool]:
    """外部フラッシュに置かれるサイズと、圧縮されたかどうか."""
    if folder not in COMPRESS_LIMIT:
        return len(data), False
    limit = COMPRESS_LIMIT[folder]
    if limit is not None and len(data) > limit:
        return len(data), False
    if folder == "gb":
        bank = 16384
        banks = [data[i:i + bank] for i in range(0, len(data), bank)]
        return (len(banks[0]) if banks else 0) + sum(_lzma(b) for b in banks[1:]), True
    if folder == "amstrad":
        return len(data), False  # dsk→cdk変換は再現しない (非圧縮で安全側に見積もる)
    return _lzma(data), True


def rom_stem(p: Path) -> str:
    """parse_roms.py と同じく、拡張子 (と圧縮拡張子) を除いた名前."""
    name = p.name
    for suf in (".lzma", ".cdk"):
        if name.lower().endswith(suf):
            name = name[: -len(suf)]
    return Path(name).stem


def cover_candidates(rom: Path) -> list[Path]:
    """ROM のカバーとして使われうる既存ファイル (parse_roms.py が探す優先順)."""
    stem = rom_stem(rom)
    found = []
    for suf in ALL_COVER_SUFFIXES:
        for cand in dict.fromkeys((suf, suf.upper(), suf.capitalize())):
            c = rom.parent / (stem + cand)
            if c.exists() and c not in found:
                found.append(c)
    return found


def find_cover(rom: Path) -> Optional[Path]:
    """実際に使われるカバー。png/jpg/bmp があればそれを変換、無ければ変換済みの .img をそのまま使う."""
    c = cover_candidates(rom)
    return c[0] if c else None


def cover_dims(folder: str) -> tuple[int, int]:
    """retro-go の roms/<機種>.json (_cover_width/_cover_height) を parse_roms.py と同じ範囲に丸める."""
    w, h = COVER_DEFAULT
    try:
        d = json.loads((C.RETROGO_REPO / "roms" / f"{folder}.json").read_text(encoding="utf-8"))
        w, h = int(d.get("_cover_width", w)), int(d.get("_cover_height", h))
    except (OSError, ValueError, TypeError):
        pass
    return min(max(w, 64), 180), min(max(h, 64), 136)


# parse_roms.py の write_covart と同じ変換 (RGB化 → LANCZOSで引き伸ばし → JPEG optimize)
_COVER_SCRIPT = r"""
import io, json, sys
from PIL import Image
out = []
for src, w, h, q in json.load(sys.stdin):
    try:
        img = Image.open(src).convert(mode="RGB").resize((w, h), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", optimize=True, quality=q)
        out.append(len(buf.getvalue()))
    except Exception as e:
        out.append(-1)
json.dump(out, sys.stdout)
"""


def convert_cover_sizes(items: list[tuple[str, int, int, int]], python: Optional[Path]) -> list[int]:
    """ビルドと同じ Pillow (tools/venv) で変換して JPEG サイズを得る。失敗時は -1."""
    if not items:
        return []
    exe = str(python) if python and python.exists() else sys.executable
    try:
        r = subprocess.run([exe, "-c", _COVER_SCRIPT], input=json.dumps(items), capture_output=True,
                           text=True, timeout=120, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        sizes = json.loads(r.stdout)
        if len(sizes) == len(items):
            return sizes
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return [-1] * len(items)


def gb_save_size(data: bytes) -> int:
    total = 4096
    cgb = data[0x143] if len(data) > 0x143 else 0
    if cgb & 0x80 or cgb == 0xC0:
        total += 8 * 4096 + 4 * 4096
    else:
        total += 2 * 4096 + 2 * 4096
    idx = data[0x149] if len(data) > 0x149 else 0
    total += ([1, 1, 1, 4, 16, 8][idx] if idx < 6 else 16) * 8 * 1024
    return total


def nes_save_size(path: Path, python: Optional[Path]) -> int:
    script = C.RETROGO_REPO / "fceumm-go" / "nesmapper.py"
    if python and python.exists() and script.exists():
        try:
            out = subprocess.run([str(python), str(script), "savesize", str(path)], cwd=C.RETROGO_REPO,
                                 capture_output=True, text=True, timeout=30,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if out.returncode == 0:
                return int(out.stdout.strip())
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
    return SAVE_SIZES["nes"]


@dataclass
class RomInfo:
    path: Path
    folder: str
    size: int
    stored: int
    compressed: bool
    save: int
    note: str = ""
    cover: Optional[Path] = None
    cover_bytes: int = 0      # 変換後 (JPEG) のサイズ。-1 は変換失敗


@dataclass
class Estimate:
    roms: list[RomInfo] = field(default_factory=list)
    base: int = 0
    emu_code: int = 0
    emu_estimated: bool = False
    images: int = 0
    rom_data: int = 0
    saves: int = 0
    total: int = 0          # EXTFLASH_SIZE
    reserved: int = 0       # config + screenshot
    capacity: int = 0       # total - saves - reserved  (ROM/コード用に残る容量)
    usage: int = 0          # base + emu + roms + images
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)       # ビルドはできるが実機で問題になりうること
    orphan_images: list[Path] = field(default_factory=list)  # 対応する ROM が無い画像
    cover_dims: dict = field(default_factory=dict)
    intflash: Optional["IntflashEstimate"] = None        # 内部フラッシュ (今の設定)
    intflash_cheat: Optional["IntflashEstimate"] = None  # 内部フラッシュ (チートを ON にした場合)

    @property
    def free(self) -> int:
        return self.capacity - self.usage

    @property
    def fits(self) -> bool:
        return not self.problems and self.free >= 0

    @property
    def tight(self) -> bool:
        return 0 <= self.free < SAFETY_MARGIN or (
            self.intflash is not None and 0 <= self.intflash.free < INTFLASH_MARGIN)


class Estimator:
    """ファイルの (サイズ, 更新時刻) をキーに圧縮結果をキャッシュする."""

    def __init__(self) -> None:
        self._cache: dict[tuple[str, int, int], tuple[int, bool, int]] = {}
        self._cover_cache: dict[tuple, int] = {}
        self._lock = threading.Lock()

    def scan(self, roms_root: Path) -> list[tuple[str, Path]]:
        found = []
        for folder, _, _ in C.ROM_SYSTEMS:
            d = roms_root / folder
            if not d.is_dir():
                continue
            for p in sorted(d.iterdir()):
                if p.is_file() and not p.name.startswith(".") and p.suffix.lower() not in SKIP_SUFFIX \
                        and p.name.lower() != "readme.md":
                    found.append((folder, p))
        return found

    def scan_images(self, roms_root: Path) -> list[tuple[str, Path]]:
        found = []
        for folder, _, _ in C.ROM_SYSTEMS:
            d = roms_root / folder
            if d.is_dir():
                found += [(folder, p) for p in sorted(d.iterdir())
                          if p.is_file() and p.suffix.lower() in IMAGE_SUFFIX]
        return found

    def signature(self, roms_root: Path) -> tuple:
        sig = []
        for folder, p in self.scan(roms_root) + self.scan_images(roms_root):
            st = p.stat()
            sig.append((str(p), st.st_size, st.st_mtime_ns))
        # チートのファイル (内部フラッシュの見積もりに使う)
        for d in [roms_root / f for f, _, _ in C.ROM_SYSTEMS] + [C.CHEATS / f for f, _, _ in C.ROM_SYSTEMS]:
            if d.is_dir():
                for p in sorted(d.iterdir()):
                    if p.suffix.lower() in CHEAT_SUFFIX:
                        st = p.stat()
                        sig.append((str(p), st.st_size, st.st_mtime_ns))
        return tuple(sig)

    def _fill_covers(self, roms: list[RomInfo], quality: int, python: Optional[Path]) -> None:
        todo = []
        for r in roms:
            if not r.cover:
                continue
            st = r.cover.stat()
            if r.cover.suffix.lower() == IMG_SUFFIX:  # 変換済み JPEG はそのまま格納される
                r.cover_bytes = st.st_size
                continue
            w, h = cover_dims(r.folder)
            key = (str(r.cover), st.st_size, st.st_mtime_ns, w, h, quality)
            with self._lock:
                cached = self._cover_cache.get(key)
            if cached is None:
                todo.append((r, key, [str(r.cover), w, h, quality]))
            else:
                r.cover_bytes = cached
        sizes = convert_cover_sizes([t[2] for t in todo], python)
        for (r, key, _), size in zip(todo, sizes):
            r.cover_bytes = size
            if size >= 0:
                with self._lock:
                    self._cover_cache[key] = size

    def _info(self, folder: str, p: Path, python: Optional[Path]) -> RomInfo:
        st = p.stat()
        key = (str(p), st.st_size, st.st_mtime_ns)
        with self._lock:
            cached = self._cache.get(key)
        if cached is None:
            data = p.read_bytes()
            stored, comp = stored_size(folder, data)
            if folder in ("nes_bios", "msx_bios"):
                save = 0
            elif folder == "gb":
                save = gb_save_size(data)
            elif folder == "nes" and p.suffix.lower() == ".nes":
                save = nes_save_size(p, python)
            else:
                save = SAVE_SIZES.get(folder, 0)
            cached = (stored, comp, align(save) if save else 0)
            with self._lock:
                self._cache[key] = cached
        stored, comp, save = cached
        note = ""
        if EXTS.get(folder) and p.suffix.lower() not in EXTS[folder]:
            note = f"拡張子 {p.suffix} はこの機種で認識されません"
        return RomInfo(p, folder, st.st_size, stored, comp, save, note)

    def estimate(self, roms_root: Path, settings: C.Settings, python: Optional[Path] = None) -> Estimate:
        est = Estimate()
        est.total = settings.retrogo_capacity()
        est.reserved = CONFIG_FLASH + (SCREENSHOT_FLASH if settings.screenshot else 0)
        used_groups: set[str] = set()
        for folder, p in self.scan(roms_root):
            info = self._info(folder, p, python)
            est.roms.append(info)
            if info.note:
                continue
            est.rom_data += info.stored
            if settings.state_saving and not p.stem.endswith("_no_save"):
                est.saves += info.save
            if folder in EMU_CODE:
                used_groups.add(EMU_GROUP.get(folder, folder))
        mappers = {m for m in (self._mapper(r.path) for r in est.roms if r.folder == "nes" and not r.note)
                   if m is not None}
        if "nes" in used_groups:
            est.emu_code += NES_MAPPER_CODE * len(mappers - {0})
        for g in used_groups:
            est.emu_code += EMU_CODE[g]
            est.emu_estimated |= g in EMU_CODE_ESTIMATED
        fixed = FIXED_COMMON + FONT_DATA.get(settings.codepage, FONT_DATA["932"])
        fixed += sum(FIXED_EMU_DATA.get(g, 0) for g in used_groups)
        est.base = align(fixed)

        # カバー画像: ROM と同名の画像を探す。変換後サイズは COVERFLOW 有効時のみ加算
        covered: set[Path] = set()
        for r in est.roms:
            cands = cover_candidates(r.path)
            r.cover = cands[0] if cands else None
            covered.update(cands)
        est.orphan_images = [p for _, p in self.scan_images(roms_root) if p not in covered]
        est.cover_dims = {r.folder: cover_dims(r.folder) for r in est.roms}
        self._fill_covers(est.roms, settings.jpg_quality, python)
        if settings.coverflow:
            est.images = sum(r.cover_bytes for r in est.roms if not r.note and r.cover_bytes > 0)
        est.usage = est.base + est.emu_code + est.rom_data + est.images
        est.capacity = est.total - est.saves - est.reserved

        folders = {r.folder for r in est.roms if not r.note}
        if not folders - {"nes_bios", "msx_bios"}:
            est.problems.append("ROMがありません (最低1つ必要)")
        if "msx" in folders:
            bad = self.check_msx_bios(roms_root)
            if bad:
                est.problems.append("MSX の BIOS が不足しています（roms\\msx_bios）: "
                                    + " / ".join(f"{n} {why}" for n, why in bad))
            elif not (roms_root / "msx_bios" / MSX_DISK_PATCHED).exists():
                # ビルド時に PANASONICDISK_.rom が生成され、BIOS として一緒に格納される
                extra = (roms_root / "msx_bios" / "PANASONICDISK.rom").stat().st_size
                est.rom_data += extra
                est.usage += extra
        self._check_fds(est, roms_root)
        self._check_names(est, roms_root, settings)
        self._check_intflash(est, roms_root, settings)
        return est

    @staticmethod
    def _check_intflash(est: Estimate, roms_root: Path, settings: C.Settings) -> None:
        """内部フラッシュ (256KB) に ROM 一覧表・表示名・チートが収まるか。超えるとリンクで失敗する."""
        from dataclasses import replace
        est.intflash = estimate_intflash(est.roms, roms_root, settings)
        est.intflash_cheat = est.intflash if settings.cheat_codes else \
            estimate_intflash(est.roms, roms_root, replace(settings, cheat_codes=True))
        ie = est.intflash
        if ie.free < 0:
            est.problems.append(f"内部フラッシュ（Retro-Go 本体 256KB）が {-ie.free:,} バイト足りません"
                                + ("（チートを減らすか、ROM を減らしてください）" if settings.cheat_codes
                                   else "（ROM を減らしてください）"))

    @staticmethod
    def _mapper(p: Path) -> Optional[int]:
        """iNES ヘッダのマッパー番号 (.fds / .nsf は None)."""
        if p.suffix.lower() != ".nes":
            return None
        try:
            with open(p, "rb") as f:
                h = f.read(16)
        except OSError:
            return None
        return ((h[6] >> 4) | (h[7] & 0xF0)) if len(h) == 16 and h[:4] == b"NES" else None

    def _sha1(self, p: Path) -> str:
        st = p.stat()
        key = ("sha1", str(p), st.st_size, st.st_mtime_ns)
        with self._lock:
            h = self._cover_cache.get(key)
        if h is None:
            h = hashlib.sha1(p.read_bytes()).hexdigest()
            with self._lock:
                self._cover_cache[key] = h
        return h

    def check_msx_bios(self, roms_root: Path) -> list[tuple[str, str]]:
        """問題のある MSX BIOS の (ファイル名, 理由) の一覧。空ならOK."""
        d = roms_root / "msx_bios"
        actual = {p.name.lower(): p for p in d.iterdir() if p.is_file()} if d.is_dir() else {}
        bad = []
        for name, (_, hashes) in MSX_BIOS.items():
            p = actual.get(name.lower())
            if p is None:
                bad.append((name, "がありません"))
            elif self._sha1(p) not in hashes:
                bad.append((name, "の中身が違います（別バージョン/破損）"))
            elif p.name != name:
                bad.append((name, f"の名前を {name} にしてください（今は {p.name}）"))
        return bad

    @staticmethod
    def _check_names(est: Estimate, roms_root: Path, settings: C.Settings) -> None:
        """日本語のファイル名・表示名がメニューでどう出るか (ビルドは sync_roms() が英数字の名前にするので通る)."""
        from .toolchain import menu_name
        names = []  # メニューに出る名前 (表示名、無ければ日本語のファイル名)
        defs: dict[str, dict] = {}
        for r in est.roms:
            if r.folder.endswith("_bios"):
                continue
            if r.folder not in defs:
                try:
                    defs[r.folder] = json.loads((roms_root / f"{r.folder}.json").read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    defs[r.folder] = {}
            stem = rom_stem(r.path)
            name = (defs[r.folder].get(stem) or {}).get("name") or stem
            if not name.isascii():
                names.append(name)
        if settings.codepage != "932":
            if names:
                est.warnings.append(f"日本語の名前が {len(names)} 件あります。メニュー言語が英語なので、"
                                    "メニューでは英数字の名前で表示されます（③構成で「日本語 (932)」にすると日本語で表示）")
            return
        bad = [n for n in names if menu_name(n, "932") != n]
        if bad:
            est.warnings.append(f"表示名に使えない文字（「表」「能」「ソ」など）があり、「_」で表示されます: "
                                + ", ".join(bad[:3]) + (f" ほか {len(bad) - 3} 件" if len(bad) > 3 else ""))

    @staticmethod
    def _check_fds(est: Estimate, roms_root: Path) -> None:
        """ディスクシステム (.fds) には roms/nes_bios/disksys.rom (8KB) が必要 (fceumm が固定名で探す)."""
        fds = [r for r in est.roms if r.folder == "nes" and r.path.suffix.lower() == ".fds" and not r.note]
        bios_dir = roms_root / "nes_bios"
        files = [p for p in bios_dir.iterdir() if p.is_file() and p.name.lower() != "readme.md"] \
            if bios_dir.is_dir() else []
        bios = next((p for p in files if p.name == FDS_BIOS), None)
        if fds and bios is None:
            wrong = [p.name for p in files if p.name.lower() == FDS_BIOS or p.suffix.lower() in (".rom", ".nes")]
            hint = f"（{', '.join(wrong)} を {FDS_BIOS} という名前にしてください）" if wrong else ""
            est.warnings.append(f"ディスクシステムのゲームが {len(fds)} 本ありますが roms\\nes_bios\\{FDS_BIOS} "
                                f"がありません。実機で起動できません{hint}")
        elif bios is not None and bios.stat().st_size != FDS_BIOS_SIZE:
            est.warnings.append(f"{FDS_BIOS} のサイズが {bios.stat().st_size} バイトです（正しくは {FDS_BIOS_SIZE} バイト）")
        elif bios is not None and not fds:
            est.warnings.append(f"ディスクシステムのゲームが無いため {FDS_BIOS} は不要です（入れたままでも動作に影響はありません）")


# ---- 内部フラッシュ (Retro-Go の本体。INTFLASH_BANK=2 で 256KB) ----
# ROM ごとに一覧表の 1 項目 (retro_emulator_file_t) と表示名の文字列が入る。チートを有効にすると、
# 項目が 16 バイト増え (id とチート用のポインタ 3 つ)、コードと説明の文字列 + ポインタ 8 バイト/個 が入る。
# 文字列は .rodata.str1.4 (1 つずつ 4 バイト境界に揃える。同じ文字列は 1 つにまとまる)。
# BIOS (nes_bios / msx_bios) も一覧表に入る。PCエンジンのチートはエスケープ (\x1\x00...) で書かれるので、
# エスケープ 1 つを 1 バイトと数える。
# 2026-09-28 の実ビルド (ゼルダ / CODEPAGE=932 / COVERFLOW=1) で計測:
#   チート無し: 229,816 = 固定 215,852 + 一覧表 231 本×44 + 表示名と拡張子の文字列 3,800 (ELF から実測)
#   チート有り: 263,088 (容量超過したビルドのリンクマップ) = 固定 + チート機能 2,596 + 一覧表 233 本×60
#               + 表示名 3,788 + チート 26,872 (113 本 745 個)。チート機能の値は、この見積もりが実測と一致するように決めた
INTFLASH_SIZE = 256 * 1024
INTFLASH_FIXED = 215_852
INTFLASH_CHEAT_CODE = 2_596     # チート機能のプログラム (メニュー・各エミュレータの適用処理)
INTFLASH_ENTRY = 44             # COVERFLOW=1 のとき。COVERFLOW=0 だと 8 バイト減る
INTFLASH_ENTRY_CHEAT = 16
INTFLASH_MARGIN = 1024          # これを切ったら「余裕が少ない」


@dataclass
class IntflashEstimate:
    fixed: int = 0
    tables: int = 0
    names: int = 0
    cheats: int = 0          # チートの文字列 + ポインタ
    cheat_roms: int = 0      # チートのある ROM の本数
    cheat_codes: int = 0     # チートの件数 (1 本 16 個まで)
    per_rom: list[tuple[Path, int]] = field(default_factory=list)  # (ROM, チートの分のバイト数)
    error: str = ""

    @property
    def usage(self) -> int:
        return self.fixed + self.tables + self.names + self.cheats

    @property
    def free(self) -> int:
        return INTFLASH_SIZE - self.usage


def _align4(n: int) -> int:
    return (n + 3) // 4 * 4


_C_CHAR = re.compile(rb"\\x[0-9A-Fa-f]+|\\[0-7]{1,3}|\\.|.", re.S)


def _cstr_size(s: bytes) -> int:
    """C の文字列リテラルとして置いたときのバイト数 (終端込み、4 バイト境界)。

    PCエンジンのチート (ROM パッチ) は "\\x1\\x00\\x07..." のようにエスケープで書き出されるので、
    エスケープ 1 つを 1 バイトと数える.
    """
    return _align4(len(_C_CHAR.findall(s)) + 1)


_parse_roms = None


def _load_parse_roms():
    """retro-go の parse_roms.py を読み込む (チートの読み取り・変換を本物と同じ処理で行うため)."""
    global _parse_roms
    if _parse_roms is None:
        import importlib.util
        import types
        spec = importlib.util.spec_from_file_location("gnw_parse_roms", C.RETROGO_REPO / "parse_roms.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.args = types.SimpleNamespace(save=False)  # ROM() が参照するグローバル

        class Utf8Path(type(Path())):
            """ビルドは PYTHONUTF8=1 なので、チートのファイルは UTF-8 で読まれる (この画面の既定は cp932)."""
            def read_text(self, encoding=None, errors=None):
                return super().read_text(encoding or "utf-8", errors)

        mod.Path = Utf8Path
        _parse_roms = mod
    return _parse_roms


def estimate_intflash(roms: list[RomInfo], roms_root: Path, settings: C.Settings) -> IntflashEstimate:
    """内部フラッシュの使用量を見積もる (ROM 一覧表・表示名・チート)."""
    import contextlib
    import io
    ie = IntflashEstimate(fixed=INTFLASH_FIXED + (INTFLASH_CHEAT_CODE if settings.cheat_codes else 0))
    entry = INTFLASH_ENTRY - (0 if settings.coverflow else 8) + (INTFLASH_ENTRY_CHEAT if settings.cheat_codes else 0)
    enc = "cp932" if settings.codepage == "932" else "cp1252"
    strings: set[bytes] = set()
    cheat_strings: set[bytes] = set()
    romdefs: dict[str, dict] = {}
    try:
        pr = _load_parse_roms() if settings.cheat_codes else None
    except Exception as e:  # noqa: BLE001 (retro-go が未取得など)
        pr, ie.error = None, f"parse_roms.py を読めません: {e}"
    targets = [r for r in roms if not r.note]  # BIOS (nes_bios / msx_bios) も一覧表に入る
    if any(r.folder == "msx_bios" for r in targets) and not (roms_root / "msx_bios" / MSX_DISK_PATCHED).exists():
        ie.tables += entry  # ビルド時に作られる PANASONICDISK_.rom も一覧表に入る
    for r in targets:
        if r.folder not in romdefs:
            try:
                romdefs[r.folder] = json.loads((roms_root / f"{r.folder}.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                romdefs[r.folder] = {}
        stem = r.path.stem
        name = (romdefs[r.folder].get(stem) or {}).get("name", stem)
        ie.tables += entry
        strings.add(name.encode(enc, "replace"))
        strings.add(r.path.suffix.lstrip(".").lower().encode())
        if pr is None:
            continue
        # チートのファイル: roms 側 → cheat_code 側 (sync_roms() と同じ優先順)
        cheat_dir = next((d for d in (r.path.parent, C.CHEATS / r.folder)
                          if any((d / (stem + s)).exists() for s in C.CHEAT_SUFFIXES)), None)
        if cheat_dir is None:
            continue
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                rom = pr.ROM(r.folder, str(cheat_dir / r.path.name), r.path.suffix.lstrip("."), {})
                codes = rom.get_cheat_codes()
        except Exception:  # noqa: BLE001 (壊れたチートのファイル: ビルドでもエラーになる)
            continue
        if not codes:
            continue
        new = {c.encode(enc, "replace") for c, _ in codes} | {d.encode(enc, "replace") for _, d in codes if d is not None}
        cost = sum(_cstr_size(s) for s in new - strings) + 8 * len(codes)
        cheat_strings.update(new - strings)
        strings.update(new)
        ie.cheats += cost
        ie.cheat_roms += 1
        ie.cheat_codes += len(codes)
        ie.per_rom.append((r.path, cost))
    ie.names = sum(_cstr_size(s) for s in strings - cheat_strings)
    return ie


USAGE_RE = re.compile(r"(Capacity|Usage|Free):\s+(-?\d+) Bytes")


def parse_build_usage(lines: list[str]) -> Optional[dict[str, int]]:
    """retro-go のビルドログ (scripts/extflash_size.sh の出力) から実測値を取り出す."""
    res: dict[str, int] = {}
    for line in lines:
        m = USAGE_RE.search(line)
        if m:
            res[m.group(1).lower()] = int(m.group(2))
    return res if len(res) == 3 else None


OVERFLOW_RE = re.compile(r"region `(\w+)' overflowed by (\d+) bytes")


def parse_overflow(lines: list[str]) -> list[tuple[str, int]]:
    return [(m.group(1), int(m.group(2))) for line in lines if (m := OVERFLOW_RE.search(line))]
