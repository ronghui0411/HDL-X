import sys
import traceback
from pathlib import Path

from hdl_x.gui.main import main


def _run() -> None:
    try:
        main()
    except Exception:
        report = traceback.format_exc()
        log_path = Path(sys.executable).with_name("HDL-X-error.log")
        try:
            log_path.write_text(report, encoding="utf-8")
        except OSError:
            pass

        try:
            from tkinter import messagebox

            messagebox.showerror(
                "HDL-X 启动失败",
                f"错误详情已写入：\n{log_path}",
            )
        except Exception:
            pass
        raise SystemExit(1) from None


if __name__ == "__main__":
    _run()
