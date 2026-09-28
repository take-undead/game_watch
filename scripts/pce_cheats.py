"""roms/pce の ROM ごとに PCエンジンのチート (.pceplus) を集め、手元の ROM で妥当性を確かめて cheat_code/pce/ に書き出す.

使い方:  tools\\venv\\Scripts\\python.exe scripts\\pce_cheats.py

.pceplus は ROM パッチ形式で、書き換え前の値を持たない (NES の 8 文字ゲームジニーのような照合はできない)。
そこで「正しい版の ROM なら、パッチ先は実際の命令の上にあり、典型的な改造の形になる」ことを使って判定する:
  - 残機などを減らす DEC/STA を、読むだけの LDA/BIT や NOP に置き換える
  - 条件分岐を、無条件分岐 (BRA) や NOP、逆の分岐に置き換える
  - LDA #n などの即値 (初期残機など) を書き換える
ゲームごとにこの形に当てはまる割合 (一致率) を出し、ランダムな位置での割合の 2 倍以上 (かつ 60% 以上) のゲームだけ採用する。
版が違う ROM では、パッチ先がでたらめなデータになるので一致率が低くなる。

出典: olderzeus/game-genie-codes-nes の pceplus フォルダ (Retro-Go の README で紹介されているもの)
"""
from __future__ import annotations

import json
import random
import re
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROMS = ROOT / "roms" / "pce"
OUT = ROOT / "cheat_code" / "pce"
CACHE = ROOT / "tools" / "cache" / "cheats"
# scripts/download_cheats.py でまとめて落としたもの (あれば先に使う)
DB = ROOT / "tools" / "cache" / "cheatdb" / "olderzeus-codes" / "pceplus"
SRC = "https://raw.githubusercontent.com/olderzeus/game-genie-codes-nes/master/pceplus/"

# ROM ファイル名 -> (日本語名, コード集のファイル名)
MAP = {
    "BIKURIMAN": ("ビックリマンワールド", "Bikkuriman World (J)"),
    "Bravoman": ("ブラボーマン (北米版)", "Bravoman (U)"),
    "DRAGON_SABER": ("ドラゴンセイバー", "Dragon Saber - After Story of Dragon Spirit (J)"),
    "DRAGON_SPIRIT": ("ドラゴンスピリット", "Dragon Spirit (J)"),
    "DRUAGA": ("ドルアーガの塔", "Tower of Druaga, The - Druaga no Tou (J)"),
    "D_TWIN_BEE": ("出たな!!ツインビー", "Detana!! TwinBee (J)"),
    "GENPEI": ("源平討魔伝", "Genpei Toumaden (J)"),
    "GRADIUS": ("グラディウス", "Gradius (J)"),
    "KIKI": ("奇々怪界", "Kiki Kaikai (J)"),
    "MERUHEN": ("メルヘンメイズ", "Marchen Maze (J)"),
    "NINJAWARRIORS": ("ニンジャウォーリアーズ", "Ninja Warriors, The (J)"),
    "PACLAND": ("パックランド", "Pac-Land (J)"),
    "PARODIUS": ("パロディウスだ!", "Parodius Da! - Shinwa kara Owarai he (J)"),
    "R-TYPE1": ("R-TYPE I", "R-Type (J)"),
    "R-TYPE2": ("R-TYPE II", "R-Type Part-2 (J)"),
    "SARAMANDA": ("沙羅曼蛇", "Salamander (J)"),
    "SIDEARMS": ("サイドアーム", "Side Arms - Hyper Dyne (J)"),
    "SPACH_HARRIER": ("スペースハリアー", "Space Harrier (J)"),
    "SPLATTER_HOUSE": ("スプラッターハウス", "Splatterhouse (J)"),
    "STARTSOLDIER": ("スーパースターソルジャー", "Super Star Soldier (J)"),
    "TERRACRESTA2": ("テラクレスタII", "Terra Cresta II - Mandrer no Gyakushuu (J)"),
    "THANDER_BLADE": ("サンダーブレード", "Thunder Blade (J)"),
    "VALKYRIE": ("ワルキューレの伝説", "Valkyrie no Densetsu (J)"),
    "WANDA_MOMO": ("ワンダーモモ", "Wonder Momo (J)"),
    "XEVIOUS": ("ゼビウス ファードラウト伝説", "Xevious - Fardraut Densetsu (J)"),
    "YOUKAIDOU": ("妖怪道中記", "Youkai Douchuuki (J) [h1]"),
}

# HuC6280 (65C02 系) の命令
BRANCH = {0x10, 0x30, 0x50, 0x70, 0x90, 0xB0, 0xD0, 0xF0, 0x80}
WRITES = {0xC6, 0xCE, 0xD6, 0xDE, 0x3A, 0xE6, 0xEE, 0xF6, 0xFE, 0x1A,          # DEC / INC
          0x85, 0x8D, 0x95, 0x9D, 0x99, 0x92, 0x81, 0x91,                      # STA
          0x86, 0x8E, 0x96, 0x84, 0x8C, 0x94, 0x64, 0x9C, 0x74, 0x9E,          # STX / STY / STZ
          0x20, 0x4C}                                                          # JSR / JMP
READS = {0xAD, 0xA5, 0xBD, 0xB5, 0xB9, 0xB2, 0x2C, 0x24, 0x3C, 0x34, 0xEA, 0x60, 0x40,   # LDA / BIT / NOP / RTS
         0xA6, 0xAE, 0xB6, 0xBE, 0xA4, 0xAC, 0xB4, 0xBC,                            # LDX / LDY
         0xC5, 0xCD, 0xD5, 0xDD, 0xD9, 0xE4, 0xEC, 0xC4, 0xCC}                      # CMP / CPX / CPY
IMMEDIATE = {0xA9, 0xA2, 0xA0, 0xC9, 0xE0, 0xC0, 0x69, 0xE9, 0x29, 0x09, 0x49, 0x89}


def load_rom(path: Path) -> bytes:
    d = bytearray(path.read_bytes())
    d = d[len(d) & 0x1FFF:]                      # 512 バイトのヘッダを除く (retro-go と同じ)
    if len(d) > 0x1FFF and d[0x1FFF] < 0xE0:     # 北米版のビット反転 (retro-go と同じ判定で解読)
        inv = [0, 8, 4, 12, 2, 10, 6, 14, 1, 9, 5, 13, 3, 11, 7, 15]
        d = bytearray((inv[b >> 4]) | (inv[b & 15] << 4) for b in d)
    return bytes(d)


def parse_line(line: str):
    """(commands[(addr, bytes)], desc) / コメントや不正行は None."""
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    parts = [p.strip() for p in line.split(",")]
    desc = parts[-1]
    cmds = []
    for p in parts[:-1]:
        if not re.fullmatch(r"[0-9A-Fa-f]{8,}", p):
            return None
        n = (int(p[0], 16)) + 1
        addr = int(p[1:6], 16)
        data = bytes.fromhex(p[6:6 + 2 * n])
        if len(data) != n:
            return None
        cmds.append((addr, data, p))
    return (cmds, desc) if cmds else None


def plausible(rom: bytes, addr: int, new: bytes) -> bool:
    if addr + len(new) > len(rom) or addr < 1:
        return False
    orig = rom[addr:addr + len(new)]
    if orig == new:
        return False                              # 何も変わらない = 版が違う疑い
    o, n, prev = orig[0], new[0], rom[addr - 1]
    if o in WRITES and n in READS:                # DEC/STA → LDA/BIT/NOP/RTS
        return True
    if o in BRANCH and (n in BRANCH or n == 0xEA):  # 分岐の変更
        return True
    if prev in IMMEDIATE and len(new) == 1:       # 即値 (LDA #n など) の変更
        return True
    if prev in BRANCH and len(new) == 1:          # 分岐先オフセットの変更
        return True
    if prev in WRITES and len(new) == 1:          # DEC/STA の番地だけを書き換えて別の場所に向ける
        return True
    if o in (0x20, 0x4C) and n in (0x20, 0x4C, 0x2C):  # 呼び出し先の差し替え / 無効化
        return True
    return False


def baseline(rom: bytes, samples: int = 4000) -> float:
    """ランダムな位置に 1 バイトのパッチを当てたときに妥当と判定される割合."""
    rnd = random.Random(1)
    hit = 0
    for _ in range(samples):
        a = rnd.randrange(1, len(rom) - 1)
        hit += plausible(rom, a, bytes([rnd.choice(sorted(READS | BRANCH))]))
    return hit / samples


def short(desc: str, limit: int = 30) -> str:
    d = re.sub(r"\s+", " ", desc).strip()
    d = d.replace("Infinite", "Inf").replace("Invincibility", "Invincible").replace("Player", "P")
    d = d.encode("ascii", "ignore").decode().replace(",", " ").strip()
    if len(d) > limit:
        cut = d[:limit + 1].rsplit(" ", 1)[0]
        d = cut if len(cut) >= limit * 0.6 else d[:limit]
    return d


def fetch(name: str) -> str | None:
    CACHE.mkdir(parents=True, exist_ok=True)
    local = DB / f"{name}.pceplus"
    if local.exists():
        return local.read_text(encoding="utf-8", errors="replace")
    f = CACHE / f"pceplus_{name}.pceplus"
    if f.exists():
        return f.read_text(encoding="utf-8", errors="replace")
    try:
        t = urllib.request.urlopen(SRC + urllib.parse.quote(name + ".pceplus"), timeout=30).read().decode("utf-8", "replace")
    except Exception:
        return None
    f.write_text(t, encoding="utf-8")
    return t


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = []
    for stem, (jname, src) in MAP.items():
        rom_path = ROMS / f"{stem}.pce"
        if not rom_path.exists():
            continue
        rom = load_rom(rom_path)
        text = fetch(src) or ""
        lines = [x for x in (parse_line(ln) for ln in text.splitlines()) if x]
        lines = [x for x in lines if "hacked version" not in x[1].lower()]   # 改造版かどうかの目印で、チートではない
        cmds = [(a, d) for c, _ in lines for a, d, _ in c]
        ok = sum(plausible(rom, a, d) for a, d in cmds)
        rate = ok / len(cmds) if cmds else 0.0
        base = baseline(rom)
        compatible = bool(cmds) and rate >= 0.6 and rate >= 2 * base
        written = []
        if compatible:
            for c, desc in lines:
                if len(written) == 16:
                    break
                written.append(",".join(raw for _, _, raw in c) + ", " + short(desc))
            (OUT / f"{stem}.pceplus").write_text("\n".join(written) + "\n", encoding="ascii")
        else:
            (OUT / f"{stem}.pceplus").unlink(missing_ok=True)
        report.append({"rom": stem, "name": jname, "source": src, "codes": len(lines), "patches": len(cmds),
                       "plausible": ok, "rate": round(rate, 3), "baseline": round(base, 3),
                       "compatible": compatible, "written": len(written)})
        print(f"{stem:15} {jname[:12]:12} codes={len(lines):2} patches={len(cmds):3} 一致率={rate:5.0%} "
              f"(ランダム {base:4.0%}) {'採用' if compatible else '不採用'}")
    json.dump(report, open(OUT / "report.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
