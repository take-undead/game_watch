import sys
import traceback


def _report(exc: BaseException) -> None:
    """pythonw で起動した場合はコンソールが無いため、エラーをダイアログとログファイルで知らせる."""
    from .config import APP_NAME, ROOT

    detail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    log = ROOT / "error.log"
    try:
        log.write_text(detail, encoding="utf-8")
    except OSError:
        pass
    try:
        from tkinter import Tk, messagebox

        root = Tk()
        root.withdraw()
        messagebox.showerror(APP_NAME, f"起動中にエラーが発生しました。\n\n{exc}\n\n詳細: {log}")
        root.destroy()
    except Exception:  # noqa: BLE001
        print(detail, file=sys.stderr)


if sys.version_info < (3, 9):
    _report(RuntimeError(f"Python 3.9 以上が必要です (現在 {sys.version.split()[0]})"))
    sys.exit(1)

try:
    from .app import main

    main()
except Exception as e:  # noqa: BLE001
    _report(e)
    sys.exit(1)
