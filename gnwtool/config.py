"""定数・パス・設定の永続化."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

APP_NAME = "G&W 改造ツール (ゼルダ / マリオ)"

ROOT = Path(__file__).resolve().parent.parent
ROMS = ROOT / "roms"
TOOLS = ROOT / "tools"
WORKSPACE = ROOT / "workspace"
SETTINGS_FILE = ROOT / "settings.json"

VENV = TOOLS / "venv"
VENV_PY = VENV / "Scripts" / "python.exe"
SHIM_BIN = TOOLS / "bin"
GCC_DIR = TOOLS / "arm-gcc"
OPENOCD_DIR = TOOLS / "openocd"

PATCH_REPO = WORKSPACE / "game-and-watch-patch"
RETROGO_REPO = WORKSPACE / "game-and-watch-retro-go"
PATCH_URL = "https://github.com/BrianPugh/game-and-watch-patch.git"
RETROGO_URL = "https://github.com/sylverb/game-and-watch-retro-go.git"

MAKE_PKG_URL = "https://mirror.msys2.org/msys/x86_64/make-4.4.1-2-x86_64.pkg.tar.zst"
# GCC 15 は C23 がデフォルトになり古いコードが壊れるため 14 系に固定
GCC_URL = (
    "https://github.com/xpack-dev-tools/arm-none-eabi-gcc-xpack/releases/download/"
    "v14.2.1-1.1/xpack-arm-none-eabi-gcc-14.2.1-1.1-win32-x64.zip"
)
OPENOCD_URL = (
    "https://github.com/xpack-dev-tools/openocd-xpack/releases/download/"
    "v0.12.0-7/xpack-openocd-0.12.0-7-win32-x64.zip"
)
GCC_MIN, GCC_MAX = 10, 14

# 機種定義。SHA1 は game-and-watch-patch/patches/{zelda,mario}.py に定義されている純正ファームの値
DEVICES = {
    "zelda": {
        "name": "ゼルダの伝説",
        "int_sha1": "ac14bcea6e4ff68c88fd2302c021025a2fb47940",
        "ext_sha1": "1c1c0ed66d07324e560dcd9e86a322ec5e4c1e96",
        "ext_hash_range": (0x20000, 0x3254A0),
        "ext_size": 4 * 1024 * 1024,
        "stock_mb": 4,
        "default_mb": 64,
        "theme": ("緑", "#1a7f37"),
        "controls": (
            "GAME = START / TIME = SELECT / PAUSE/SET = メニュー\n"
            "本体の START・SELECT ボタンは追加ボタン (X/Y) として使われます（メガドライブ・MSX等）"
        ),
    },
    "mario": {
        "name": "スーパーマリオブラザーズ",
        "int_sha1": "efa04c387ad7b40549e15799b471a6e1cd234c76",
        "ext_sha1": "eea70bb171afece163fb4b293c5364ddb90637ae",
        "ext_hash_range": (0, 1024 * 1024 - 8192),
        "ext_size": 1024 * 1024,
        "stock_mb": 1,
        "default_mb": 1,
        "theme": ("赤", "#cf222e"),
        "controls": (
            "GAME = START / TIME = SELECT / PAUSE/SET = メニュー\n"
            "START・SELECT ボタンが無いため、追加ボタンが必要なゲームは一部操作が組み合わせ押しになります"
        ),
    },
}
INT_SIZE = 128 * 1024


def backup_names(device: str) -> tuple[str, str]:
    return f"internal_flash_backup_{device}.bin", f"flash_backup_{device}.bin"


def flash_sizes(device: str) -> dict[int, str]:
    stock = DEVICES[device]["stock_mb"]
    sizes = {stock: f"{stock}MB (純正チップのまま)"}
    sizes.update({mb: f"{mb}MB" for mb in (16, 32, 64, 128)})
    return sizes


CODEPAGES = {
    "1252": "英語/欧州 (1252)",
    "932": "日本語 (932)",
}

# (フォルダ名, 表示名, 拡張子)
ROM_SYSTEMS = [
    ("nes", "ファミコン / NES", ".nes .fds .nsf"),
    ("nes_bios", "ディスクシステムBIOS", ".rom .nes"),
    ("gb", "ゲームボーイ / カラー", ".gb .gbc"),
    ("pce", "PCエンジン", ".pce"),
    ("sms", "セガ マークIII / マスターシステム", ".sms"),
    ("gg", "ゲームギア", ".gg"),
    ("sg", "SG-1000", ".sg"),
    ("md", "メガドライブ", ".md .gen .bin"),
    ("col", "コレコビジョン", ".col"),
    ("msx", "MSX", ".rom .mx1 .mx2 .dsk"),
    ("msx_bios", "MSX BIOS", ".rom"),
    ("gw", "LCDゲーム&ウオッチ", ".gw"),
    ("wsv", "スーパービジョン", ".bin .sv"),
    ("a7800", "Atari 7800", ".a78 .bin"),
    ("amstrad", "Amstrad CPC", ".dsk"),
    ("tama", "たまごっち", ".b"),
]


@dataclass
class Settings:
    device: str = "zelda"
    backup_dirs: dict = field(default_factory=lambda: {
        d: str(ROOT / "backup_rom" / f"backup_{d}") for d in DEVICES})
    flash_mbs: dict = field(default_factory=lambda: {d: v["default_mb"] for d, v in DEVICES.items()})
    # パッチ(純正側)オプション: Zelda
    no_second_beep: bool = False
    no_hour_tune: bool = False
    # パッチ(純正側)オプション: Mario  (容量を増設している場合のみ有効)
    mario_keep_extras: bool = False
    # Retro-Go オプション
    codepage: str = "1252"
    coverflow: bool = False
    jpg_quality: int = 90
    cover_pad: bool = True  # カバー編集で画像の外側 (黒い余白) も範囲にできる
    cover_pad_fill: str = "#000000"  # 余白の塗り: '#rrggbb' または 'blur'
    cheat_codes: bool = False
    state_saving: bool = True
    screenshot: bool = False
    disable_splash: bool = False
    clean_build: bool = True
    # ⑤ で書き込む内容 (改造済みの本体では Retro-Go だけを書くことが多い)
    write_stock: bool = True
    write_retrogo: bool = True
    migrate_saves: bool = True
    # 機種ごとに、最後に書き込んだ保存ビルド {device: {"package": ファイル名, "written": 日時}}
    last_written: dict = field(default_factory=dict)
    extra_retrogo_args: str = ""

    @classmethod
    def load(cls) -> "Settings":
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        # 旧バージョン (Zelda 専用) の設定を引き継ぐ
        if "backup_dir" in data:
            data.setdefault("backup_dirs", {})["zelda"] = data.pop("backup_dir")
        if "flash_mb" in data:
            data.setdefault("flash_mbs", {})["zelda"] = data.pop("flash_mb")
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        try:
            s = cls(**known)
        except TypeError:
            return cls()
        base = cls()
        s.backup_dirs = {**base.backup_dirs, **(s.backup_dirs or {})}
        s.flash_mbs = {**base.flash_mbs, **(s.flash_mbs or {})}
        if s.device not in DEVICES:
            s.device = "zelda"
        return s

    def save(self) -> None:
        SETTINGS_FILE.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- 機種ごとの値 ---------------------------------------------------
    @property
    def dev(self) -> dict:
        return DEVICES[self.device]

    @property
    def backup_dir(self) -> str:
        return self.backup_dirs[self.device]

    @backup_dir.setter
    def backup_dir(self, value: str) -> None:
        self.backup_dirs[self.device] = value

    @property
    def flash_mb(self) -> int:
        return int(self.flash_mbs[self.device])

    @flash_mb.setter
    def flash_mb(self, value: int) -> None:
        self.flash_mbs[self.device] = int(value)

    @property
    def is_stock_flash(self) -> bool:
        return self.flash_mb == self.dev["stock_mb"]

    # ---- 派生パラメータ -------------------------------------------------
    def mario_uses_ext(self) -> bool:
        """Mario で純正ファームの一部を外部フラッシュ先頭1MBに残すか."""
        return self.device == "mario" and self.mario_keep_extras and not self.is_stock_flash

    def patch_params(self) -> str:
        if self.device == "mario":
            # README: --internal-only で純正ファームを内部フラッシュだけに収め、外部フラッシュを空ける
            #         (スリープ画像・マリオの歌の隠し要素は削除される)
            return "--device=mario" if self.mario_uses_ext() else "--device=mario --internal-only"
        params = ["--device=zelda"]
        if self.is_stock_flash:
            # docs/zelda.md: 純正4MBではLA・スリープ画像を削除して空きを作る
            params += ["--no-la", "--no-sleep-images"]
        if self.no_second_beep:
            params.append("--no-second-beep")
        if self.no_hour_tune:
            params.append("--no-hour-tune")
        return " ".join(params)

    def extflash_layout(self) -> tuple[int, int]:
        """Retro-Go に割り当てる (サイズ, オフセット) [bytes]."""
        mb = 1024 * 1024
        if self.device == "mario":
            if self.mario_uses_ext():
                return (self.flash_mb - 1) * mb, mb
            return self.flash_mb * mb, 0
        if self.is_stock_flash:
            return 1794048, 860160
        return (self.flash_mb - 4) * mb, 4 * mb

    def retrogo_vars(self) -> list[str]:
        size, offset = self.extflash_layout()
        v = [f"GNW_TARGET={self.device}", "INTFLASH_BANK=2", "ADAPTER=stlink",
             f"EXTFLASH_SIZE={size}", f"EXTFLASH_OFFSET={offset}"]
        v.append(f"CODEPAGE={self.codepage}")
        v.append(f"COVERFLOW={int(self.coverflow)}")
        v.append(f"JPG_QUALITY={int(self.jpg_quality)}")
        v.append(f"CHEAT_CODES={int(self.cheat_codes)}")
        v.append(f"STATE_SAVING={int(self.state_saving)}")
        v.append(f"ENABLE_SCREENSHOT={int(self.screenshot)}")
        v.append(f"DISABLE_SPLASH_SCREEN={int(self.disable_splash)}")
        v += self.extra_retrogo_args.split()
        return v

    def retrogo_capacity(self) -> int:
        return self.extflash_layout()[0]
