"""roms/nes の ROM ごとにチートコードを集め、手元の ROM と照合して cheat_code/nes/<ROM名>.ggcodes を作る.

使い方:  tools\venv\Scripts\python.exe scripts\nes_cheats.py
  - ROM を追加したら MAP に「ファイル名 → (日本語名, 日本版/日米共通の libretro ファイル, 北米版の参考ファイル)」を足す
  - 出典: libretro-database (cht/Nintendo - Nintendo Entertainment System) と
          martaaay/game-and-watch-retro-go-game-genie-codes、一部はファミコンチート集 Wiki (MANUAL)
  - 判定: ok=8文字コードの比較値が ROM と一致 / plausible=6文字コードの置換元命令が典型パターン /
          trusted=日本版・日米共通版向けとして公開されたコード (RAM 書き換えなど ROM で照合できないもの)
"""


import re

LETTERS = "APZLGITYEOXUKSVN"


def decode_gg(code: str):
    """(address, value, compare or None) / 不正なら None."""
    code = code.upper()
    if len(code) not in (6, 8) or any(c not in LETTERS for c in code):
        return None
    n = [LETTERS.index(c) for c in code]
    address = 0x8000 + (((n[3] & 7) << 12) | ((n[5] & 7) << 8) | ((n[4] & 8) << 8)
                        | ((n[2] & 7) << 4) | ((n[1] & 8) << 4) | (n[4] & 7) | (n[3] & 8))
    if len(code) == 6:
        value = ((n[1] & 7) << 4) | ((n[0] & 8) << 4) | (n[0] & 7) | (n[5] & 8)
        return address, value, None
    value = ((n[1] & 7) << 4) | ((n[0] & 8) << 4) | (n[0] & 7) | (n[7] & 8)
    compare = ((n[7] & 7) << 4) | ((n[6] & 8) << 4) | (n[6] & 7) | (n[5] & 8)
    return address, value, compare


class Rom:
    def __init__(self, path):
        d = open(path, "rb").read()
        h = d[:16]
        self.mapper = (h[6] >> 4) | (h[7] & 0xF0)
        trainer = 512 if h[6] & 4 else 0
        self.prg = d[16 + trainer:16 + trainer + h[4] * 16384]

    def candidates(self, addr: int) -> list[int]:
        """CPU アドレスに割り当たりうる PRG 内オフセットの一覧."""
        size = len(self.prg)
        rel = addr - 0x8000
        m = self.mapper
        if size <= 32768 and m in (0, 3, 87, 185, 70):
            return [rel % size]
        if m in (2, 94, 73, 70, 71, 180):          # 16KB 切替 + 最終16KB固定
            if addr >= 0xC000:
                return [size - 16384 + (rel - 0x4000)]
            return [b * 16384 + rel for b in range(size // 16384)]
        if m in (1,):                               # MMC1: 16KB / 32KB モード
            off = rel & 0x3FFF
            return [b * 16384 + off for b in range(size // 16384)]
        if m in (66, 11, 7, 34):                    # 32KB 切替
            return [b * 32768 + rel for b in range(max(1, size // 32768))]
        off = rel & 0x1FFF                          # MMC3 / VRC など 8KB 単位
        if m in (4, 25) and addr >= 0xE000:
            return [size - 8192 + off]
        return [b * 8192 + off for b in range(size // 8192)]

    def check(self, addr: int, compare: int) -> int:
        """compare の値が見つかったバンク数 (0 なら不一致)."""
        return sum(1 for o in self.candidates(addr) if 0 <= o < len(self.prg) and self.prg[o] == compare)


RAW = re.compile(r"^([0-9A-F]{4})(?:\?([0-9A-F]{2}))?:([0-9A-F]{2})$")


def verify_part(rom: Rom, part: str):
    """1 つのコードを判定: ('rom-ok' | 'rom-ng' | 'gg6' | 'ram' | 'bad', 詳細)."""
    part = part.strip().upper()
    g = decode_gg(part)
    if g:
        addr, val, cmp_ = g
        if cmp_ is None:
            return "gg6", f"{addr:04X}={val:02X}"
        hits = rom.check(addr, cmp_)
        return ("rom-ok" if hits else "rom-ng"), f"{addr:04X}?{cmp_:02X}={val:02X} hits={hits}"
    m = RAW.match(part)
    if m:
        addr = int(m.group(1), 16)
        if addr >= 0x8000:
            if m.group(2):
                hits = rom.check(addr, int(m.group(2), 16))
                return ("rom-ok" if hits else "rom-ng"), part
            return "gg6", part
        return "ram", part
    return "bad", part


ZP_OPS = [0xA5, 0x85, 0xC6, 0xE6, 0xB5, 0x95, 0xA6, 0x86, 0xA4, 0x84, 0x65, 0xE5, 0xC5, 0x25, 0x05, 0x45, 0x06, 0x46, 0x26, 0x66, 0xD6, 0xF6]
ABS_OPS = [0xAD, 0x8D, 0xCE, 0xEE, 0xBD, 0x9D, 0xB9, 0x99, 0xAE, 0x8E, 0xAC, 0x8C, 0x6D, 0xED, 0xCD, 0x2D, 0x0D, 0xDE, 0xFE]


def ram_refs(rom: Rom, addr: int) -> int:
    """その RAM アドレスを直接読み書きする命令が ROM に何か所あるか (0 でも添字アクセスの可能性あり)."""
    prg = rom.prg
    n = 0
    if addr < 0x100:
        for op in ZP_OPS:
            n += prg.count(bytes([op, addr]))
    for op in ABS_OPS:
        n += prg.count(bytes([op, addr & 0xFF, addr >> 8]))
    return n


import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ROMS = ROOT / "roms" / "nes"
OUT = ROOT / "cheat_code" / "nes"
CACHE = ROOT / "tools" / "cache" / "cheats"
# scripts/download_cheats.py でまとめて落としたもの (あれば先に使う)
DB_LIBRETRO = ROOT / "tools" / "cache" / "cheatdb" / "libretro-database" / "cht" / "Nintendo - Nintendo Entertainment System"
DB_MARTAAAY = ROOT / "tools" / "cache" / "cheatdb" / "martaaay-ggcodes" / "ggcodes"
LIBRETRO = ("https://raw.githubusercontent.com/libretro/libretro-database/master/cht/"
            "Nintendo%20-%20Nintendo%20Entertainment%20System/")
MARTAAAY = "https://raw.githubusercontent.com/martaaay/game-and-watch-retro-go-game-genie-codes/HEAD/ggcodes/"

# ROM -> (日本語名, [日本版/日米共通の libretro ファイル], [北米版の参考ファイル (8文字のみ採用)])
MAP = {
    "BABEL": ("バベルの塔", ["Babel no Tou (Japan)"], []),
    "BALLOON_FIGHT": ("バルーンファイト", ["Balloon Fight (Japan)"], ["Balloon Fight (World) (Game Genie)"]),
    "BOKOSUKA": ("ボコスカウォーズ", ["Bokosuka Wars (Japan)"], []),
    "BOMBAERMAN": ("ボンバーマン", ["Bomber Man (Japan)"], ["Bomberman (USA) (Game Genie)"]),
    "B_TAKESHI": ("たけしの挑戦状", ["Takeshi no Chousenjou (Japan)"], []),
    "CHALENGER": ("チャレンジャー", ["Challenger (Japan) (Game Genie)", "Challenger (Japan)"], []),
    "Clu Clu Land": ("クルクルランド", ["Clu Clu Land (World) (Game Genie)", "Clu Clu Land (World)"], []),
    "DEVIL_WORLD": ("デビルワールド", ["Devil World (Japan) (Rev 1)"], []),
    "DIG_DUG": ("ディグダグ", ["Dig Dug (Japan) (Game Genie)", "Dig Dug (Japan)"], []),
    "DIG_DUG2": ("ディグダグII", ["Dig Dug II (Japan)"], ["Dig Dug II - Trouble in Paradise (USA) (Game Genie)"]),
    "DONKEEY_KONG": ("ドンキーコング", ["Donkey Kong (Japan)"], ["Donkey Kong (World) (Game Genie)"]),
    "DONKEY3": ("ドンキーコング3", ["Donkey Kong 3 (World) (Game Genie)", "Donkey Kong 3 (World)"], []),
    "DONKEY_JR": ("ドンキーコングJR.", ["Donkey Kong Jr. (Japan)"], ["Donkey Kong Jr. (World) (Rev 1)"]),
    "DRACULA": ("悪魔城ドラキュラ", ["Akumajou Dracula (Japan)"], ["Castlevania (USA) (Game Genie)"]),
    "DRAEMON": ("ドラえもん", [], []),
    "DRAGON_QUEST": ("ドラゴンクエスト", [], ["Dragon Warrior (USA) (Game Genie)"]),
    "DRAGON_QUEST2": ("ドラゴンクエストII", [], ["Dragon Warrior II (USA) (Game Genie)"]),
    "DRAGON_QUEST3": ("ドラゴンクエストIII", [], ["Dragon Warrior III (USA) (Game Genie)"]),
    "DRAGON_SLAYER4": ("ドラゴンスレイヤーIV", [], ["Legacy of the Wizard (USA) (Game Genie)"]),
    "DRUAGA": ("ドルアーガの塔", ["Druaga no Tou (Japan)"], []),
    "GALAGA": ("ギャラガ", ["Galaga (Japan)"], ["Galaga - Demons of Death (USA) (Game Genie)"]),
    "GARIUS2": ("魔城伝説II 大魔司教ガリウス", ["Majou Densetsu II - Daimashikyou Galious (Japan)"], []),
    "GRADIUS": ("グラディウス", ["Gradius (Japan)"], ["Gradius (World) (Game Genie)"]),
    "GRADIUS2": ("グラディウスII", ["Gradius II (Japan) (Game Genie)", "Gradius II (Japan)"], []),
    "HOKUTO1": ("北斗の拳", ["Hokuto no Ken (Japan)"], []),
    "HOKUTO2": ("北斗の拳2", ["Hokuto no Ken 2 (Japan)"], ["Fist of the North Star (USA) (Game Genie)"]),
    "HYDLIDE": ("ハイドライド・スペシャル", [], ["Hydlide (USA) (Game Genie)"]),
    "KAGE_D": ("影の伝説", [], ["Legend of Kage, The (USA) (Game Genie)"]),
    "KANFU": ("イー・アル・カンフー", ["Yie Ar Kung-Fu (Japan) (Game Genie)", "Yie Ar Kung-Fu (Japan) (Rev 1.4)"], []),
    "KEKYOKU": ("けっきょく南極大冒険", ["Kekkyoku Nankyoku Daibouken (Japan)"], []),
    "LIPURU_ILAND": ("リップルアイランド", [], []),
    "LOAD_RUNNER": ("ロードランナー", ["Lode Runner (USA, Japan) (Game Genie)", "Lode Runner (Japan)"], []),
    "MACROSS": ("超時空要塞マクロス", ["Choujikuu Yousai - Macross (Japan)"], []),
    "MAKAIMURA": ("魔界村", ["Makaimura (Japan)"], []),
    "MAPPY": ("マッピー", ["Mappy (Japan)"], []),
    "MEIKYU": ("迷宮組曲", ["Meikyuu Kumikyoku - Milon no Daibouken (Japan)"], ["Milon's Secret Castle (USA) (Game Genie)"]),
    "META_FIGHT": ("超惑星戦記メタファイト", ["Chou-Wakusei Senki - MetaFight (Japan)"], ["Blaster Master (USA) (Game Genie)"]),
    "NATU-MILK": ("ナッツ&ミルク", ["Nuts _ Milk (Japan) (Game Genie)", "Nuts _ Milk (Japan)"], []),
    "OOKAMI": ("戦場の狼", [], ["Commando (USA) (Game Genie)"]),
    "Okhotsk ni Kiyu": ("オホーツクに消ゆ", [], []),
    "PACMAN": ("パックマン", ["Pac-Man (Japan) (En)", "Pac-Man (Japan) (En) (Rev A)"], ["Pac-Man (World) (Game Genie)"]),
    "ROMANCIA": ("ロマンシア", ["Romancia (Japan)"], []),
    "SANMA": ("さんまの名探偵", [], []),
    "SARAMANDA": ("沙羅曼蛇", ["Salamander (Japan)"], ["Life Force (USA) (Game Genie)"]),
    "SKYKID": ("スカイキッド", ["Sky Kid (USA, Japan) (Game Genie)", "Sky Kid (USA)"], []),
    "SOLOMON": ("ソロモンの鍵", [], ["Solomon's Key (USA, Europe) (Game Genie)"]),
    "SPALTANX": ("スパルタンX", ["Spartan X (Japan)", "Kung Fu (World) (Game Genie)", "Kung Fu (Japan, USA)"], []),
    "SPELUNKER": ("スペランカー", ["Spelunker (Japan)", "Spelunker (USA, Japan) (Game Genie)"], []),
    "STAR_FOACE": ("スターフォース", ["Star Force (Japan)", "Star Force (World) (Game Genie)"], []),
    "STAR_SOLDIER": ("スターソルジャー", ["Star Soldier (USA, Japan) (Game Genie)", "Star Soldier (USA)"], []),
    "STAR_WARS": ("スター・ウォーズ (ナムコ)", ["Star Wars (Japan) (Namco)"], []),
    "S_MARIO": ("スーパーマリオブラザーズ", ["Super Mario Bros. (World) (Game Genie)", "Super Mario Bros. (World)"], []),
    "S_MARIO3": ("スーパーマリオブラザーズ3", [], ["Super Mario Bros. 3 (USA) (Game Genie)"]),
    "S_XEVIOUS": ("スーパーゼビウス ガンプの謎", ["Super Xevious - Gump no Nazo (Japan) (Game Genie)",
                                                 "Super Xevious - Gump no Nazo (Japan)"], []),
    "TATAKAI": ("闘いの挽歌", ["Tatakai no Banka (Japan) (Game Genie)", "Tatakai no Banka (Japan) (Rev 1)"], []),
    "TERRA_CRESTA": ("テラクレスタ", ["Terra Cresta (USA, Japan) (Game Genie)", "Terra Cresta (USA)"], []),
    "THEXDER": ("テグザー", ["Thexder (Japan)"], []),
    "WARPMAN": ("ワープマン", ["Warpman (Japan)"], []),
    "WRECKING_CREW": ("レッキングクルー", ["Wrecking Crew (World) (Game Genie)", "Wrecking Crew (World)"], []),
    "XEVIUS": ("ゼビウス", ["Xevious (Japan) (En)", "Xevious (Japan) (En) (Rev 1)"], ["Xevious - The Avenger (USA) (Game Genie)"]),
    "YS1": ("イース", ["Ys (Japan)"], []),
    "YS2": ("イースII", ["Ys II - Ancient Ys Vanished - The Final Chapter (Japan)"], []),
    "ZELDA": ("ゼルダの伝説", [], ["Legend of Zelda, The (USA, Europe) (Game Genie)"]),
    "ZGUNDAM": ("機動戦士Zガンダム ホットスクランブル", ["Kidou Senshi Z Gundam - Hot Scramble (Japan)"], []),
    "gegege": ("ゲゲゲの鬼太郎 妖怪大魔境", ["Gegege no Kitarou - Youkai Daimakyou (Japan)"], []),
    "goonies": ("グーニーズ", ["Goonies (Japan)"], []),
    "goonies2": ("グーニーズ2", ["Goonies 2 - Fratelli Saigo no Chousen (Japan) (Action Replay)"],
                 ["Goonies II, The (USA, Europe) (Game Genie)"]),
    "saradanokuni": ("サラダの国のトマト姫", [], ["Princess Tomato in the Salad Kingdom (USA)"]),
}

# martaaay/game-and-watch-retro-go-game-genie-codes の北米版タイトル (8文字コード / 根拠のある6文字のみ採用)
US_TITLES = {
 "BALLOON_FIGHT": "Balloon Fight",
 "BOMBAERMAN": "Bomberman",
 "Clu Clu Land": "Clu Clu Land",
 "DIG_DUG2": "Dig Dug II",
 "DONKEEY_KONG": "Donkey Kong",
 "DONKEY3": "Donkey Kong 3",
 "DRACULA": "Castlevania",
 "DRAGON_QUEST": "Dragon Warrior",
 "DRAGON_QUEST2": "Dragon Warrior 2",
 "DRAGON_QUEST3": "Dragon Warrior 3",
 "DRAGON_SLAYER4": "Legacy of the Wizard",
 "GALAGA": "Galaga Demons of Death",
 "GRADIUS": "Gradius",
 "HOKUTO2": "Fist of the North Star",
 "HYDLIDE": "Hydlide",
 "KAGE_D": "The Legend of Kage",
 "LOAD_RUNNER": "Lode Runner",
 "MAKAIMURA": "Ghosts'n Goblins",
 "MEIKYU": "Milon's Secret Castle",
 "META_FIGHT": "Blaster Master",
 "OOKAMI": "Commando",
 "PACMAN": "Pac Man",
 "SARAMANDA": "Life Force",
 "SKYKID": "Sky Kid",
 "SOLOMON": "Solomon's Key",
 "SPALTANX": "Kung Fu",
 "SPELUNKER": "Spelunker",
 "STAR_SOLDIER": "Star Soldier",
 "S_MARIO": "Super Mario Bros",
 "S_MARIO3": "Super Mario Bros 3",
 "TATAKAI": "Trojan",
 "WRECKING_CREW": "Wrecking Crew",
 "XEVIUS": "Xevious",
 "ZELDA": "The Legend of Zelda",
 "goonies2": "Goonies 2",
 "TERRA_CRESTA": "Terra Cresta"
}

# 6文字コードの根拠: 「減らす/書き込む命令」を「読むだけの命令」などに置き換える典型パターン
PLAUSIBLE = {
    0xAD: {0xCE, 0xEE, 0x8D, 0x8E, 0x8C},  # LDA abs  <- DEC/INC/STA/STX/STY abs
    0xA5: {0xC6, 0xE6, 0x85, 0x86, 0x84},  # LDA zp   <- DEC/INC/STA/STX/STY zp
    0xBD: {0xDE, 0xFE, 0x9D},              # LDA abs,X <- DEC/INC/STA abs,X
    0xB5: {0xD6, 0xF6, 0x95},              # LDA zp,X  <- DEC/INC/STA zp,X
    0x2C: {0xCE, 0xEE, 0x8D, 0x20, 0x4C},  # BIT abs  <- DEC/INC/STA/JSR/JMP (命令を潰す)
    0x24: {0xC6, 0xE6, 0x85},              # BIT zp
    0xEA: set(range(256)),                 # NOP は判断不能 → 除外 (下で処理)
}


# libretro に無いものを日本のサイトから補う (RAM コード)。出典: ファミコンチート集 Wiki
MANUAL = {
    "DRAGON_QUEST": ("wikiwiki.jp/nnnes1 (ファミコンチート集 Wiki)", [
        ("00BC:FF+00BD:FF", "Gold 65535"),
        ("00BA:FF+00BB:FF", "EXP 65535 (max level)"),
        ("00C5:FF", "HP 255"),
        ("00C6:FF", "MP 255"),
        ("00BF:06", "Keys x6"),
        ("00C0:06", "Herbs x6"),
        ("0094:FF+0095:FF", "Fewer encounters"),
        ("00E2:00", "Enemy dies in one hit"),
    ]),
    # 002A/002B は Wiki (002A-1-09, 002B-2-0020)、ステージ別は ameblo.jp/grannaska/entry-12865856022.html。
    # ROM で確認: $2A は DEC して負ならゲームオーバー、$2B は被弾で減り、満タン = (8 - $2C) * 4 (= $20)。
    # ステージ別の番地は他のステージで別の用途に使われるので、そのステージ以外では外すこと。
    "DRAEMON": ("wikiwiki.jp/nnnes1 + ameblo.jp/grannaska", [
        ("002A:09", "Lives 9"),
        ("002B:20+002C:00", "Full HP"),
        ("0079:12", "Stage1 Invincible"),
        ("007B:03", "Stage1 Power Uchiwa"),
        ("0084:FF", "Stage1 Max rapid fire"),
        ("00A0:10", "Stage2 Invincible"),
        ("007C:03", "Stage2 Gian + Small Light"),
        ("0080:03", "Stage2 Hirari Mantle"),
    ]),
}


def fetch(url: str, dest: Path, local: Path | None = None) -> str | None:
    if local and local.exists():
        return local.read_text(encoding="utf-8", errors="replace")
    if dest.exists():
        return dest.read_text(encoding="utf-8", errors="replace")
    try:
        data = urllib.request.urlopen(url, timeout=30).read().decode("utf-8", errors="replace")
    except Exception:
        return None
    dest.write_text(data, encoding="utf-8")
    return data


def parse_cht(text: str) -> list[tuple[str, str]]:
    descs = dict(re.findall(r'cheat(\d+)_desc\s*=\s*"([^"]*)"', text))
    codes = dict(re.findall(r'cheat(\d+)_code\s*=\s*"([^"]*)"', text))
    return [(codes[k], descs.get(k, "")) for k in sorted(codes, key=int)]


def parse_ggcodes(text: str) -> list[tuple[str, str]]:
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "//")):
            continue
        code, _, desc = line.partition(",")
        out.append((code.strip(), desc.strip()))
    return out


ABBR = [
    (r"\bInfinite\b", "Inf"), (r"\bUnlimited\b", "Inf"), (r"\bInvincibility\b", "Invincible"),
    (r"\bDon'?t\b", "No"), (r"\bDo not\b", "No"), (r"\bNever\b", "No"),
    (r"\bStart (?:the game )?(?:with|With|on|On|at|At)\b", "Start w/"), (r"\bInstead of\b", "not"),
    (r"\bPlayer ?1\b", "P1"), (r"\bPlayer ?2\b", "P2"), (r"\bplayers?\b", "P"), (r"\bPlayers?\b", "P"),
    (r"\bHealth\b", "HP"), (r"\bEnergy\b", "Energy"), (r"\bExperience\b", "EXP"), (r"\bPoints\b", "pts"),
    (r"\bLevel\b", "Lv"), (r"\bLives\b", "lives"), (r"\bMaximum\b", "Max"), (r"\bMinimum\b", "Min"),
    (r"\bAmmunition\b", "Ammo"), (r"\bWeapons?\b", "weapon"), (r"\bSecond\b", "2nd"), (r"\bFirst\b", "1st"),
    (r"\b(?:The|A|An|Your|Of|Is|Are)\b ?", ""), (r"\s+for\s+free\b", " free"),
]
PRIORITY = [
    r"invinc|invulner|no damage|don'?t take damage|one.hit|never die",
    r"inf\w*.*(lives|life|men)|lives|life|men\b|1.?up|continues",
    r"energy|health|\bhp\b|\bmp\b|power|life bar|stamina",
    r"time|timer|clock",
    r"weapon|ammo|bomb|shot|missile|laser|option|fire|sword|arrow|magic",
    r"gold|money|coins?|rupee|score|points|exp",
    r"stage|level|world|round|area|floor|warp|skip",
    r"jump|speed|fast|run|fly|walk through",
]
LOW = r"music|sound|default value|color|palette|debug|glitch|weird|funny|graphics"


def priority(desc: str) -> int:
    d = desc.lower()
    if re.search(LOW, d):
        return 99
    for i, pat in enumerate(PRIORITY):
        if re.search(pat, d):
            return i
    return 50


def short(desc: str, limit: int = 30) -> str:
    d = re.sub(r"\s+", " ", desc).strip()
    if len(d) > limit:
        for pat, rep in ABBR:
            d = re.sub(pat, rep, d)
        d = re.sub(r"\s+", " ", d).strip()
    if len(d) > limit:
        d = re.sub(r"\s*\([^)]*\)", "", d).strip()
    d = d.encode("ascii", "ignore").decode().replace(",", " ").strip()
    if len(d) > limit:
        cut = d[:limit + 1].rsplit(" ", 1)[0]
        d = cut if len(cut) >= limit * 0.6 else d[:limit]
    return d.rstrip(" -:;.")


def judge(rom: Rom, code: str, trusted: bool):
    """行全体の判定: ('ok' | 'plausible' | 'trusted' | None, 理由)."""
    parts = [p for p in re.split(r"[+,;\s]+", code.strip()) if p]
    if not parts or len(parts) > 3:
        return None, "parts"
    kinds = []
    for p in parts:
        kind, info = verify_part(rom, p)
        if kind in ("rom-ng", "bad"):
            return None, f"{p}:{kind}"
        if kind == "gg6":
            g = decode_gg(p)
            if g is None:  # raw 形式の ROM 書き換え (比較値なし)
                if not trusted:
                    return None, f"{p}:unverified"
                kinds.append("trusted")
                continue
            addr, val, _ = g
            origs = {rom.prg[o] for o in rom.candidates(addr) if 0 <= o < len(rom.prg)}
            if val != 0xEA and val in PLAUSIBLE and origs & PLAUSIBLE[val]:
                kinds.append("plausible")
            elif trusted:
                kinds.append("trusted")
            else:
                return None, f"{p}:gg6-unverified"
        elif kind == "ram":
            if not trusted:
                return None, f"{p}:ram-from-other-version"
            kinds.append("trusted")
        else:
            kinds.append("ok")
    rank = {"ok": 0, "plausible": 1, "trusted": 2}
    return max(kinds, key=rank.get), ""


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    report = []
    for stem, (jname, jp_files, us_files) in MAP.items():
        rom_path = ROMS / f"{stem}.nes"
        if not rom_path.exists():
            continue
        rom = Rom(rom_path)
        cands = []  # (code, desc, source, trusted)
        for f in jp_files:
            t = fetch(LIBRETRO + urllib.parse.quote(f + ".cht"), CACHE / f"{f}.cht", DB_LIBRETRO / f"{f}.cht")
            if t:
                cands += [(c, d, f, True) for c, d in parse_cht(t)]
        for f in us_files:
            t = fetch(LIBRETRO + urllib.parse.quote(f + ".cht"), CACHE / f"{f}.cht", DB_LIBRETRO / f"{f}.cht")
            if t:
                cands += [(c, d, f, False) for c, d in parse_cht(t)]
        mt = fetch(MARTAAAY + urllib.parse.quote(US_TITLES[stem] + ".ggcodes"),
                   CACHE / f"martaaay_{stem}.ggcodes",
                   DB_MARTAAAY / (re.sub(r'[\\:*?"<>|]', "_", US_TITLES[stem]) + ".ggcodes")) if stem in US_TITLES else None
        if mt:
            cands += [(c, d, "martaaay (USA)", False) for c, d in parse_ggcodes(mt)]

        if stem in MANUAL:
            src, codes = MANUAL[stem]
            cands += [(c, d, src, True) for c, d in codes]
        seen, accepted, rejected = set(), [], 0
        for code, desc, src, trusted in cands:
            key = code.upper().replace(" ", "")
            if key in seen or not desc:
                continue
            seen.add(key)
            level, why = judge(rom, code, trusted)
            if level is None:
                rejected += 1
                continue
            accepted.append((level, key, short(desc), src, desc))
        order = {"ok": 0, "plausible": 1, "trusted": 2}
        # 役に立つ種類を優先し、同じ種類の中では照合の強いものから
        accepted.sort(key=lambda x: (priority(x[2]), order[x[0]]))
        # 同じ説明の重複を除き、16 個まで
        # 種類ごとに最大 3 個 → 余った枠を残りで埋める (同じ説明は除く)
        final, descs, per = [], set(), {}
        for cap in (3, 16):
            for a in accepted:
                if len(final) == 16:
                    break
                if a in final or not a[2] or a[2].lower() in descs:
                    continue
                pr = priority(a[4])
                if per.get(pr, 0) >= cap:
                    continue
                per[pr] = per.get(pr, 0) + 1
                descs.add(a[2].lower())
                final.append(a)
        if final:
            (OUT / f"{stem}.ggcodes").write_text(
                "".join(f"{code}, {desc}\n" for _, code, desc, _, _ in final), encoding="ascii")
        report.append({
            "rom": stem, "name": jname, "mapper": rom.mapper, "written": len(final), "rejected": rejected,
            "levels": {k: sum(1 for f in final if f[0] == k) for k in order},
            "sources": sorted({f[3] for f in final}),
            "codes": [(lv, c, d, full) for lv, c, d, _, full in final],
        })
    json.dump(report, open(OUT / "report.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for r in report:
        print(f"{r['rom']:16} {r['name'][:14]:14} written={r['written']:2} ok={r['levels']['ok']:2} "
              f"plaus={r['levels']['plausible']:2} trusted={r['levels']['trusted']:2} rejected={r['rejected']:3}")


if __name__ == "__main__":
    main()
