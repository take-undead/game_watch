"""チートの説明文の日本語化を、集め直し (nes_cheats.py / pce_cheats.py) で失わないための補助.

cheat_code/ のファイルは UTF-8 で保存する (ビルドの parse_roms.py は PYTHONUTF8=1 で読む)。
書き出す前に、既存のファイルにある日本語の説明をコードごとに読み取り、英語の出典名の代わりに使う。
"""
import hashlib
import json
from pathlib import Path


def find_rom(roms_dir: Path, stem: str, exts: tuple[str, ...]) -> Path | None:
    """チートの名前 (MAP のキー) に対応する ROM. 同じ名前が無ければ cheat_code/<機種>/roms.json
    ({ROM の SHA1: チートの名前}) で、名前を変えた ROM を中身から探す (gnwtool.toolchain.cheat_for と同じ)."""
    files = [p for p in roms_dir.iterdir() if p.is_file() and p.suffix.lower() in exts] if roms_dir.is_dir() else []
    for ext in exts:  # 拡張子の優先順 (例: .nes → .fds)
        hit = next((p for p in files if p.stem == stem and p.suffix.lower() == ext), None)
        if hit:
            return hit
    try:
        idx = json.loads((roms_dir.parent.parent / "cheat_code" / roms_dir.name / "roms.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    want = {h for h, name in idx.items() if name == stem}
    return next((p for p in files if want and hashlib.sha1(p.read_bytes()).hexdigest() in want), None)


def _key(line: str, suffix: str) -> tuple[str, str]:
    """(コード, 説明). .ggcodes は最初の , で、.pceplus は最後の , で分ける."""
    code, _, desc = line.rpartition(",") if suffix == ".pceplus" else line.partition(",")
    return "".join(code.split()).upper(), desc.strip()


def japanese_descs(path: Path) -> dict[str, str]:
    """既存のファイルから {コード: 日本語の説明} を読む (ASCII だけの説明は含めない)."""
    try:
        raw = path.read_bytes()
    except OSError:
        return {}
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("cp932", "replace")
    out = {}
    for line in text.splitlines():
        code, desc = _key(line, path.suffix)
        if code and desc and not desc.isascii():
            out[code] = desc
    return out


def localize(path: Path, lines: list[str]) -> str:
    """書き出す行の説明を、既存のファイルの日本語の説明で置き換えた本文."""
    ja = japanese_descs(path)
    out = []
    for line in lines:
        code, desc = _key(line, path.suffix)
        if code in ja:
            head = line.rpartition(",")[0] if path.suffix == ".pceplus" else line.partition(",")[0]
            line = f"{head}, {ja[code]}"
        out.append(line)
    return "".join(f"{ln}\n" for ln in out)
