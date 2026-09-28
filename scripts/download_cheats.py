"""チートコードの出典を tools/cache/cheatdb/ にまとめてダウンロード (2 回目以降は更新).

使い方:  tools\venv\Scripts\python.exe scripts\download_cheats.py
  - nes_cheats.py / pce_cheats.py は、ここにあるファイルを先に読む (無ければ 1 本ずつネットから取る)
  - libretro-database は大きい (cht 全体で 160MB 超) ので、使う機種のフォルダだけを sparse checkout する
  - 小さいリポジトリは zip で取る。Windows で使えない文字を含むファイル名 (例: "Q*Bert.ggcodes") があり、
    git checkout ではそこで止まるため。使えない文字は "_" に置き換える
"""
import io
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "tools" / "cache" / "cheatdb"

LIBRETRO = ("libretro-database", "https://github.com/libretro/libretro-database.git", [
    "cht/Nintendo - Nintendo Entertainment System",
    "cht/Nintendo - Family Computer Disk System",
    "cht/NEC - PC Engine - TurboGrafx 16",
    "cht/Microsoft - MSX",
    "cht/Microsoft - MSX2",
])
# (フォルダ名, GitHub の owner/repo)
ZIPS = [
    ("martaaay-ggcodes", "martaaay/game-and-watch-retro-go-game-genie-codes"),
    ("olderzeus-codes", "olderzeus/game-genie-codes-nes"),
]


def git(*args: str, cwd: Path | None = None) -> None:
    print("> git", " ".join(args), flush=True)
    subprocess.run(["git", *args], cwd=cwd, check=True)


def get_libretro() -> None:
    name, url, paths = LIBRETRO
    dest = DB / name
    if (dest / ".git").exists():
        git("pull", "--ff-only", "--depth=1", cwd=dest)
        return
    git("clone", "--depth=1", "--filter=blob:none", "--sparse", url, str(dest))
    git("sparse-checkout", "set", *paths, cwd=dest)


def get_zip(name: str, repo: str) -> None:
    url = f"https://codeload.github.com/{repo}/zip/HEAD"
    print(f"> {url}", flush=True)
    data = urllib.request.urlopen(url, timeout=120).read()
    dest = DB / name
    if dest.exists():
        shutil.rmtree(dest)
    n = 0
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            parts = info.filename.split("/")[1:]  # 先頭の "<repo>-<hash>/" を外す
            out = dest.joinpath(*[re.sub(r'[\\:*?"<>|]', "_", p) for p in parts])
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(z.read(info))
            n += 1
    print(f"  {n} files -> {dest}")


def main() -> None:
    DB.mkdir(parents=True, exist_ok=True)
    get_libretro()
    for name, repo in ZIPS:
        get_zip(name, repo)
    print(f"完了: {DB}")


if __name__ == "__main__":
    sys.exit(main())
