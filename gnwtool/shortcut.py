"""アイコン付きのショートカットを作成する (python -m gnwtool.shortcut)."""
from __future__ import annotations

import base64
import subprocess
import sys
from pathlib import Path

from . import config as C

NAME = "GnW改造ツール.lnk"
ICON = Path(__file__).resolve().parent / "assets" / "app.ico"
EXE = C.ROOT / "GnW改造ツール.exe"  # 持ち運び版の起動用 (scripts/make_portable.py が作る)


def _pythonw() -> Path:
    exe = Path(sys.executable)
    cand = exe.with_name("pythonw.exe")
    return cand if cand.exists() else exe


def _ps_quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def create(desktop: bool = True) -> list[Path]:
    """プロジェクトフォルダ (と任意でデスクトップ) にショートカットを作り、作成したパスを返す."""
    script = f"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$ws = New-Object -ComObject WScript.Shell
$dirs = @({_ps_quote(str(C.ROOT))})
if (${'true' if desktop else 'false'}) {{ $dirs += [Environment]::GetFolderPath('Desktop') }}
foreach ($dir in $dirs) {{
  $lnk = Join-Path $dir {_ps_quote(NAME)}
  $s = $ws.CreateShortcut($lnk)
  $s.TargetPath = {_ps_quote(str(EXE if EXE.exists() else _pythonw()))}
  $s.Arguments = {_ps_quote("" if EXE.exists() else "-m gnwtool")}
  $s.WorkingDirectory = {_ps_quote(str(C.ROOT))}
  $s.IconLocation = {_ps_quote(str(ICON))}
  $s.Description = {_ps_quote(C.APP_NAME)}
  $s.Save()
  [Console]::Out.WriteLine($lnk)
}}
"""
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded],
                       capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    out = r.stdout.decode("utf-8", errors="replace") if r.stdout else ""
    if r.returncode != 0:
        err = r.stderr.decode("cp932", errors="replace")
        raise RuntimeError(f"ショートカットの作成に失敗しました:\n{err.strip()}")
    paths = [Path(p) for p in out.splitlines() if p.strip()]
    missing = [p for p in paths if not p.exists()]
    if not paths or missing:
        raise RuntimeError("ショートカットの作成を確認できませんでした。")
    return paths


if __name__ == "__main__":
    from tkinter import Tk, messagebox

    root = Tk()
    root.withdraw()
    try:
        made = create()
        messagebox.showinfo(C.APP_NAME, "ショートカットを作成しました。\n\n" + "\n".join(map(str, made))
                            + "\n\n次回からはデスクトップの「GnW改造ツール」をダブルクリックで起動できます。")
    except Exception as e:  # noqa: BLE001
        messagebox.showerror(C.APP_NAME, str(e))
        sys.exit(1)
