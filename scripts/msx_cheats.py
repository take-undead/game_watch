"""roms/msx の ROM ごとに blueMSX のチート (MCF) を選び、手元の ROM と照合して cheat_code/msx/<ROM名>.mcf を作る.

使い方:  tools\venv\Scripts\python.exe scripts\msx_cheats.py
  - ROM を追加したら MAP に「ファイル名 (拡張子なし) → (日本語名, [MCF の候補])」を足す
  - 出典: blueMSX の Cheats.zip (Retro-Go の README が案内しているもの。公式サイトは 404 なので archive.org から取る)
  - MCF は RAM の値を固定するコード (Retro-Go は RAM の読み出しを差し替える)。ROM に書き換え前の値が無いので、
    「その番地を Z80 の命令が直接読み書きしているか」をゲームごとに数え、ランダムな番地での割合と比べて版の一致を判定する
  - 判定: ok=その番地を直接読み書きする命令が ROM にある / trusted=版が一致したファイルにあるが直接の参照は無い
          (IX+d などの添字アクセス)。版が一致しないファイルは使わない
"""

import io
import json
import random
import re
import urllib.request
import zipfile
from pathlib import Path

from cheat_ja import find_rom

ROOT = Path(__file__).resolve().parent.parent
ROMS = ROOT / "roms" / "msx"
OUT = ROOT / "cheat_code" / "msx"
# scripts/download_cheats.py でまとめて落としたもの
DB = ROOT / "tools" / "cache" / "cheatdb" / "bluemsx" / "Cheats" / "msx"
ZIP_URL = "https://web.archive.org/web/2015id_/http://bluemsx.msxblue.com/rel_download/Cheats.zip"

# ROM (拡張子なし) -> (日本語名, [MCF の候補 (版の一致率が高いものを使う)])
MAP = {
    "Aleste (1988)(Compile)(Jp)": ("アレスタ", ["aleste1"]),
    "Chack N Pop (1984)(Taito)": ("チャックンポップ", ["chacknpop"]),
    "Dig Dug (1982-84)(Namcot)": ("ディグダグ", ["digdug"]),
    "Dragon Buster (1987)(Namcot)[b]": ("ドラゴンバスター", ["dragonbuster"]),
    "Dragon Slayer 4 - Drasle Family (1987)(Falcom)": ("ドラゴンスレイヤーIV", ["dragonslayer4msx1", "dragonslayer4msx2"]),
    "Goonies, The (1986)(Konami)[a][RC-734]": ("グーニーズ", ["goonies"]),
    "Hydlide II - Shine Of Darkness (1985)(T&E Soft)": ("ハイドライドII", ["hydlide2"]),
    "King Knight (1986)(Square)[b]": ("キングスナイト", ["kingsknight"]),
    "Knight Mare II - The Maze Of Galious (1987)(Konami)[RC-749]": ("魔城伝説II ガリウスの迷宮", ["mazeofgalious"]),
    "MAJYOUDE": ("魔城伝説", ["knightmare"]),
    "Majutsushi Mahjong 2 (1989)(Konami)(Jp)[RC-765]": ("麻雀悟空 / 魔術師麻雀 2", []),
    "Metal Gear (1987)(Konami)[RC-750]": ("メタルギア", ["metalgear1"]),
    "Metal Gear 2 - Solid Snake (1990)(Konami)[RC-767]": ("メタルギア2 ソリッドスネーク", ["metalgear2"]),
    "Nemesis (1986)(Konami)[a][RC-742]": ("グラディウス", ["gradius1", "gradius1scc"]),
    "Nemesis II (1987)(Konami)[a][RC-751]": ("グラディウス2", ["gradius2"]),
    "Nemesis III - The Eve Of Destruction (1988)(Konami)[a][RC-764]": ("ゴーファーの野望 エピソードII", ["nemesis3"]),
    "Ninjakun (1984)(Jaleco)(Jp)": ("忍者くん", ["ninjakun1", "ninjakun2"]),
    "Relics (19xx)(-)[b]": ("レリクス", []),
    "Romancia - Dragon Slayer Jr (19xx)(Falcom)[b]": ("ロマンシア", ["romancia"]),
    "Salamander (1988)(Zemina)[RC-758]": ("沙羅曼蛇", ["salamander"]),
    "Spelunker (1986)(Irem Corp)": ("スペランカー", ["spelunker"]),
    "Star Soldier (1986)(Hudson Soft)": ("スターソルジャー", ["starsoldier"]),
    "Tank Batallion (1980-84)(Namcot)": ("タンクバタリアン", ["tankbattalion"]),
    # topplezipmsx1 は 3 番地のうち 1 つしか参照が無く、版の一致を確かめられない
    "Topple Zip 2 (1988)(Bothtec)": ("トップルジップ", []),
    "Tower Of Druaga, The (1984-86)(Namcot)": ("ドルアーガの塔", ["towerofdrauga"]),
    "Valis - The Fantasm Soldier (1987)(Zemina)": ("夢幻戦士ヴァリス", ["fantasmsoldier1"]),
    "Volguard (1985)(DB Soft)": ("ボルガード", ["volguard"]),
    "Warp & Warp (1980-84)(Namcot)": ("ワープ&ワープ", ["warpwarp"]),
    "Yie Ar Kung-Fu (1985)(Konami)[RC-725]": ("イー・アル・カンフー", ["yiearkungfu1"]),
    "Yie Ar Kung-Fu II - The Emperor Yie-Gah (1985)(Konami)[a][RC-737]": ("イー・アル・カンフーII", ["yiearkungfu2"]),
}

# Z80 で 16 ビットの番地を直接持つ命令 (番地の前に置かれるバイト列)
REF_OPS = [
    b"\x3a", b"\x32",                                  # LD A,(nn) / LD (nn),A
    b"\x2a", b"\x22",                                  # LD HL,(nn) / LD (nn),HL
    b"\x21", b"\x11", b"\x01",                         # LD HL/DE/BC,nn (ポインタ)
    b"\xed\x4b", b"\xed\x43", b"\xed\x5b", b"\xed\x53", b"\xed\x7b", b"\xed\x73",
    b"\xdd\x2a", b"\xdd\x22", b"\xfd\x2a", b"\xfd\x22",
    b"\xdd\x21", b"\xfd\x21",                          # LD IX/IY,nn
]


def refs(rom: bytes, addr: int) -> int:
    """その番地を直接扱う命令が ROM に何か所あるか."""
    lo_hi = bytes([addr & 0xFF, addr >> 8])
    return sum(rom.count(op + lo_hi) for op in REF_OPS)


def near_refs(rom: bytes, addr: int) -> bool:
    """構造体の先頭 (少し手前の番地) を LD HL/IX,nn などで指していれば、添字アクセスとみなす."""
    return any(refs(rom, a) for a in range(addr - 8, addr + 1))


def baseline(rom: bytes, lo: int, hi: int, n: int = 400) -> float:
    """同じ範囲のランダムな番地で、直接の参照がある割合."""
    rnd = random.Random(0)
    return sum(1 for _ in range(n) if refs(rom, rnd.randrange(lo, hi))) / n


def load_db() -> None:
    if DB.exists():
        return
    print(f"> {ZIP_URL}", flush=True)
    data = urllib.request.urlopen(ZIP_URL, timeout=180).read()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extractall(DB.parent.parent)


def parse_mcf(text: str) -> list[tuple[int, int, str]]:
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("!"):
            continue
        parts = line.split(",", 4)
        if len(parts) == 5 and parts[1].strip().isdigit() and parts[2].strip().isdigit():
            out.append((int(parts[1]), int(parts[2]), parts[4].strip()))
    return out


# 役に立つ種類から順に (NES / PCE と同じ考え方)
PRIORITY = [
    r"invinc|invuln|protect|immortal|no damage|untouch|one hit|dies after",
    r"lives|life\b|lifes|men\b|players? left|continue",
    r"vitality|energy|power|health|\bhp\b|\bmp\b|stamina|fuel|oxygen|vit\b",
    r"time|timer",
    r"weapon|ammo|bomb|shot|shoot|missile|laser|option|arrow|sword|fire|magic|shield|double|beam|bullet|gun",
    r"gold|money|coin|key|exp|score|jewel|item|potion|card",
    r"speed",
]
# 値を固定すると進行が止まる・見た目だけ・意味が分からないもの
SKIP = (r"stage|level|round|world|area|scene|floor|room|location|pos\b|x-pos|y-pos|position|color|colour|"
        r"mode|simulate|demo|music|sound|activator|decrease|debug|select|choose|only for|map\b|direction|"
        r"maze|mission|planet|finished|as enemy|disable|deactivate|in game player|player 2|put in slot")


def priority(desc: str) -> int:
    d = desc.lower()
    if re.search(SKIP, d):
        return 99
    for i, pat in enumerate(PRIORITY):
        if re.search(pat, d):
            return i
    return 50


def short(desc: str, limit: int = 30) -> str:
    d = re.sub(r"\s+", " ", desc).strip()
    d = d.encode("ascii", "ignore").decode().replace(",", " ").strip(" -:;.")
    d = d[:1].upper() + d[1:]
    if len(d) > limit:
        d = re.sub(r"\s*\([^)]*\)", "", d).strip()
    if len(d) > limit:
        cut = d[:limit + 1].rsplit(" ", 1)[0]
        d = cut if len(cut) >= limit * 0.6 else d[:limit]
    return d.rstrip(" -:;.")


def merge(entries: list[tuple[int, int, str]]) -> list[tuple[int, int, str]]:
    """同じ説明で隣り合う 2 バイト (例: arrows 57414=153, 57415=9) を 1 つの 2 バイトのコードにまとめる.

    同じ番地に値違いが並ぶもの (武器の種類など) は、最後の 1 つ (たいてい一番強いもの) だけを残す.
    """
    last = {}
    for a, v, d in entries:
        last[a] = (a, v, d)
    items = sorted(last.values())
    out, i = [], 0
    while i < len(items):
        a, v, d = items[i]
        if (i + 1 < len(items) and items[i + 1][0] == a + 1 and items[i + 1][2].strip().lower() == d.strip().lower()
                and v <= 0xFF and items[i + 1][1] <= 0xFF):
            out.append((a, v | items[i + 1][1] << 8, d))
            i += 2
            continue
        out.append((a, v, d))
        i += 1
    return out


def main():
    load_db()
    OUT.mkdir(parents=True, exist_ok=True)
    report = []
    for stem, (jname, mcfs) in MAP.items():
        rom_path = find_rom(ROMS, stem, (".rom",))  # 名前を変えた ROM も中身から探す
        if rom_path is None:
            continue
        rom = rom_path.read_bytes()
        best = None  # (一致率, ファイル名, エントリ, ランダム時の割合)
        for name in mcfs:
            f = DB / f"{name}.mcf"
            if not f.exists():
                continue
            entries = merge(parse_mcf(f.read_text(encoding="cp1252", errors="replace")))
            ram = [e for e in entries if e[0] >= 0x8000]
            if not ram:
                continue
            addrs = sorted({a for a, _, _ in ram})
            ratio = sum(1 for a in addrs if refs(rom, a)) / len(addrs)
            # ランダムな番地は RAM 全体から取る (カートリッジのゲームは 8KB なら $E000-、16KB なら $C000- を使う)
            lo = 0xE000 if addrs[0] >= 0xE000 else 0xC000 if addrs[0] >= 0xC000 else 0x8000
            base = baseline(rom, lo, max(0xF380, addrs[-1] + 1))
            if best is None or ratio > best[0]:
                best = (ratio, name, ram, base)
        rec = {"rom": stem, "name": jname, "written": 0}
        report.append(rec)
        if best is None:
            rec["note"] = "no source"
            continue
        ratio, name, ram, base = best
        rec.update(mcf=name, ratio=round(ratio, 2), random=round(base, 2))
        # 版の一致: 直接の参照がある番地の割合が「ランダムな番地の 2 倍以上かつ 30% 以上」か「3 倍以上かつ 20% 以上」
        if ratio < max(0.3, base * 2) and not (ratio >= 0.2 and ratio >= base * 3):
            rec["note"] = "version mismatch"
            continue
        cands = []
        for a, v, d in ram:
            pr = priority(d)
            if pr == 99 or not d:
                continue
            level = "ok" if refs(rom, a) else ("trusted" if near_refs(rom, a) else None)
            if level is None:
                continue
            cands.append((pr, level != "ok", a, v, short(d), level))
        cands.sort()
        final, descs, per = [], set(), {}
        for cap in (3, 16):  # 種類ごとに最大 3 個 → 余った枠を残りで埋める
            for c in cands:
                if len(final) == 16:
                    break
                if c in final or c[4].lower() in descs or per.get(c[0], 0) >= cap:
                    continue
                per[c[0]] = per.get(c[0], 0) + 1
                descs.add(c[4].lower())
                final.append(c)
        final.sort(key=lambda c: (c[0], c[2]))
        if final:
            (OUT / f"{stem}.mcf").write_text(
                f"!cheats for blueMSX: {name} (blueMSX Cheats.zip)\n"
                + "".join(f"0,{a},{v},0,{d}\n" for _, _, a, v, d, _ in final), encoding="ascii")
        rec["written"] = len(final)
        rec["levels"] = {k: sum(1 for c in final if c[5] == k) for k in ("ok", "trusted")}
        rec["codes"] = [(c[5], c[2], c[3], c[4]) for c in final]
    json.dump(report, open(OUT / "report.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for r in report:
        print(f"{r['rom'][:40]:40} {r.get('mcf', '-'):18} ratio={r.get('ratio', '-')!s:5} "
              f"rand={r.get('random', '-')!s:5} written={r['written']:2} {r.get('note', '')}")


if __name__ == "__main__":
    main()
