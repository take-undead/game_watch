"""チートの説明文の日本語化を、集め直し (nes_cheats.py / pce_cheats.py) で失わないための補助.

cheat_code/ のファイルは UTF-8 で保存する (ビルドの parse_roms.py は PYTHONUTF8=1 で読む)。
書き出す前に、既存のファイルにある日本語の説明をコードごとに読み取り、英語の出典名の代わりに使う。
"""
from pathlib import Path


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
