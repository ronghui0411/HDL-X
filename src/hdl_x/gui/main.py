"""HDL-X Tkinter 桌面应用。"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from hdl_x.transformer import NameStyle

from .controller import (
    ConversionReport,
    ConversionRequest,
    GuiInputError,
    execute_conversion,
    format_gui_error,
    inspect_environment_report,
    suggest_output_path,
    validate_conversion_request,
)


@dataclass(frozen=True, slots=True)
class _WorkerMessage:
    """后台转换线程向 Tk 主线程传递的单条消息。"""

    report: ConversionReport | None = None
    error: Exception | None = None


class HDLXApplication(ttk.Frame):
    """VHDL → Verilog-2001 桌面转换界面。"""

    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master, padding=16)
        self.master = master
        self.source_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.mode = tk.StringVar(value="strict")
        self.name_style = tk.StringVar(value=NameStyle.PRESERVE.value)
        self.validate_output = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="就绪")
        self._last_suggested_output: Path | None = None
        self._busy = False
        self._messages: queue.Queue[_WorkerMessage] = queue.Queue()

        self._configure_window()
        self._build_widgets()
        self._bind_shortcuts()

    def _configure_window(self) -> None:
        """配置窗口尺寸和原生主题。"""

        self.master.title("HDL-X — VHDL → Verilog-2001")
        self.master.geometry("1180x780")
        self.master.minsize(900, 620)
        self.master.protocol("WM_DELETE_WINDOW", self._close_window)

        style = ttk.Style(self.master)
        themes = style.theme_names()
        if "vista" in themes:
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Subtitle.TLabel", foreground="#4a5568")
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(18, 8))

        self.grid(row=0, column=0, sticky="nsew")
        self.master.rowconfigure(0, weight=1)
        self.master.columnconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

    def _build_widgets(self) -> None:
        """创建文件、选项、预览和诊断区域。"""

        header = ttk.Frame(self)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="HDL-X", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="将受支持的 VHDL-2008 RTL 转换为可读的 Verilog-2001",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        files = ttk.LabelFrame(self, text="文件", padding=10)
        files.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        files.columnconfigure(1, weight=1)
        ttk.Label(files, text="VHDL 输入").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.source_entry = ttk.Entry(files, textvariable=self.source_path)
        self.source_entry.grid(row=0, column=1, sticky="ew")
        self.source_button = ttk.Button(files, text="浏览…", command=self._choose_source)
        self.source_button.grid(row=0, column=2, padx=(8, 0))

        ttk.Label(files, text="Verilog 输出").grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=(8, 0)
        )
        self.output_entry = ttk.Entry(files, textvariable=self.output_path)
        self.output_entry.grid(row=1, column=1, sticky="ew", pady=(8, 0))
        self.output_button = ttk.Button(files, text="另存为…", command=self._choose_output)
        self.output_button.grid(row=1, column=2, padx=(8, 0), pady=(8, 0))

        options = ttk.LabelFrame(self, text="转换选项", padding=10)
        options.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        options.columnconfigure(7, weight=1)
        ttk.Label(options, text="模式").grid(row=0, column=0, sticky="w")
        self.strict_button = ttk.Radiobutton(
            options,
            text="严格",
            variable=self.mode,
            value="strict",
        )
        self.strict_button.grid(row=0, column=1, padx=(8, 4))
        self.best_effort_button = ttk.Radiobutton(
            options,
            text="尽力转换",
            variable=self.mode,
            value="best_effort",
        )
        self.best_effort_button.grid(row=0, column=2, padx=4)

        ttk.Separator(options, orient="vertical").grid(
            row=0, column=3, sticky="ns", padx=12
        )
        ttk.Label(options, text="名称风格").grid(row=0, column=4, sticky="w")
        self.name_style_box = ttk.Combobox(
            options,
            textvariable=self.name_style,
            values=[style.value for style in NameStyle],
            state="readonly",
            width=14,
        )
        self.name_style_box.grid(row=0, column=5, padx=(8, 12))
        self.validate_button = ttk.Checkbutton(
            options,
            text="调用可用验证器",
            variable=self.validate_output,
        )
        self.validate_button.grid(row=0, column=6, padx=(0, 12))

        self.doctor_button = ttk.Button(options, text="检查环境", command=self._show_environment)
        self.doctor_button.grid(row=0, column=8, padx=(4, 8))
        self.convert_button = ttk.Button(
            options,
            text="开始转换",
            style="Primary.TButton",
            command=self._start_conversion,
        )
        self.convert_button.grid(row=0, column=9)

        workspace = ttk.Panedwindow(self, orient="horizontal")
        workspace.grid(row=3, column=0, sticky="nsew")
        source_panel = ttk.LabelFrame(workspace, text="VHDL 源码预览", padding=6)
        output_panel = ttk.LabelFrame(workspace, text="Verilog 输出预览", padding=6)
        workspace.add(source_panel, weight=1)
        workspace.add(output_panel, weight=1)
        self.source_preview = self._create_text_panel(source_panel)
        self.output_preview = self._create_text_panel(output_panel)

        diagnostics = ttk.LabelFrame(self, text="状态与诊断", padding=6)
        diagnostics.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        diagnostics.columnconfigure(0, weight=1)
        self.log = tk.Text(
            diagnostics,
            height=7,
            wrap="word",
            relief="flat",
            background="#f7fafc",
            foreground="#1a202c",
            padx=8,
            pady=6,
        )
        log_scroll = ttk.Scrollbar(diagnostics, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=log_scroll.set)
        self.log.grid(row=0, column=0, sticky="ew")
        log_scroll.grid(row=0, column=1, sticky="ns")
        self._set_text(self.log, "选择一个 VHDL 文件，然后点击“开始转换”。")

        footer = ttk.Frame(self)
        footer.grid(row=5, column=0, sticky="ew", pady=(8, 0))
        footer.columnconfigure(0, weight=1)
        ttk.Label(footer, textvariable=self.status).grid(row=0, column=0, sticky="w")
        self.progress = ttk.Progressbar(footer, mode="indeterminate", length=180)
        self.progress.grid(row=0, column=1, sticky="e")

    def _create_text_panel(self, parent: ttk.LabelFrame) -> tk.Text:
        """创建带滚动条的等宽只读文本框。"""

        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        text = tk.Text(
            parent,
            wrap="none",
            font=("Consolas", 10),
            undo=False,
            padx=8,
            pady=8,
        )
        vertical = ttk.Scrollbar(parent, orient="vertical", command=text.yview)
        horizontal = ttk.Scrollbar(parent, orient="horizontal", command=text.xview)
        text.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        text.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        text.configure(state="disabled")
        return text

    def _bind_shortcuts(self) -> None:
        """注册不影响文本编辑的常用快捷键。"""

        self.master.bind("<Control-o>", lambda _event: self._choose_source())
        self.master.bind("<Control-s>", lambda _event: self._choose_output())
        self.master.bind("<Control-Return>", lambda _event: self._start_conversion())
        self.master.bind("<F5>", lambda _event: self._start_conversion())

    def _choose_source(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.master,
            title="选择 VHDL 源文件",
            filetypes=[("VHDL 源文件", "*.vhd *.vhdl"), ("所有文件", "*.*")],
        )
        if not path:
            return
        source = Path(path)
        previous_output = self.output_path.get().strip()
        if not previous_output or (
            self._last_suggested_output is not None
            and Path(previous_output) == self._last_suggested_output
        ):
            suggestion = suggest_output_path(source)
            self.output_path.set(str(suggestion))
            self._last_suggested_output = suggestion
        self.source_path.set(str(source))
        self._load_source_preview(source)

    def _choose_output(self) -> None:
        initial = self.output_path.get().strip()
        initial_path = Path(initial) if initial else None
        path = filedialog.asksaveasfilename(
            parent=self.master,
            title="选择 Verilog 输出文件",
            defaultextension=".v",
            initialdir=str(initial_path.parent) if initial_path else None,
            initialfile=initial_path.name if initial_path else None,
            filetypes=[("Verilog-2001", "*.v"), ("所有文件", "*.*")],
        )
        if path:
            self.output_path.set(path)
            self._last_suggested_output = None

    def _load_source_preview(self, path: Path) -> None:
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            self._set_text(self.source_preview, "")
            self._set_text(self.log, f"无法读取源码预览：{error}")
            return
        self._set_text(self.source_preview, content)
        self.status.set(f"已载入 {path.name}")

    def _show_environment(self) -> None:
        if self._busy:
            return
        try:
            report = inspect_environment_report()
        except Exception as error:
            self._set_text(self.log, format_gui_error(error))
            self.status.set("环境检查失败")
            return
        self._set_text(self.log, report.text)
        if report.required_available:
            self.status.set("必需环境可用")
        else:
            self.status.set("缺少必需环境")
            messagebox.showwarning(
                "HDL-X 环境检查",
                "缺少必需的 frontend。请查看状态与诊断区域。",
                parent=self.master,
            )

    def _start_conversion(self) -> None:
        if self._busy:
            return
        try:
            request = validate_conversion_request(self._build_request())
        except (GuiInputError, ValueError) as error:
            messagebox.showerror("输入无效", str(error), parent=self.master)
            return
        if request.output_path.exists() and not messagebox.askyesno(
            "覆盖输出文件",
            f"输出文件已存在：\n{request.output_path}\n\n是否覆盖？",
            parent=self.master,
        ):
            return

        self._set_busy(True)
        self._set_text(self.log, "正在解析 VHDL、执行语义检查并生成 Verilog…")
        self.status.set("正在转换…")
        worker = threading.Thread(
            target=self._conversion_worker,
            args=(request,),
            name="hdl-x-gui-conversion",
            daemon=True,
        )
        worker.start()
        self.after(100, self._poll_worker)

    def _build_request(self) -> ConversionRequest:
        source_text = self.source_path.get().strip()
        output_text = self.output_path.get().strip()
        if not source_text:
            raise GuiInputError("请选择输入 VHDL 文件。")
        if not output_text:
            raise GuiInputError("请选择 Verilog 输出文件。")
        return ConversionRequest(
            source_path=Path(source_text),
            output_path=Path(output_text),
            strict=self.mode.get() == "strict",
            name_style=NameStyle(self.name_style.get()),
            validate=self.validate_output.get(),
        )

    def _conversion_worker(self, request: ConversionRequest) -> None:
        try:
            report = execute_conversion(request)
        except Exception as error:
            self._messages.put(_WorkerMessage(error=error))
            return
        self._messages.put(_WorkerMessage(report=report))

    def _poll_worker(self) -> None:
        try:
            message = self._messages.get_nowait()
        except queue.Empty:
            if self._busy:
                self.after(100, self._poll_worker)
            return

        self._set_busy(False)
        if message.error is not None:
            rendered = format_gui_error(message.error)
            self._set_text(self.log, rendered)
            self.status.set("转换失败")
            messagebox.showerror("HDL-X 转换失败", rendered, parent=self.master)
            return
        assert message.report is not None
        self._show_conversion_report(message.report)

    def _show_conversion_report(self, report: ConversionReport) -> None:
        self._set_text(self.output_preview, report.result.text)
        lines = [f"转换完成：{report.output_path}"]
        lines.extend(diagnostic.format() for diagnostic in report.result.diagnostics)
        if not report.result.diagnostics:
            lines.append("没有非致命诊断。")
        self._set_text(self.log, "\n".join(lines))
        self.status.set(f"转换完成：{report.output_path.name}")
        messagebox.showinfo(
            "HDL-X",
            f"Verilog 已生成：\n{report.output_path}",
            parent=self.master,
        )

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        for widget in (
            self.source_entry,
            self.output_entry,
            self.source_button,
            self.output_button,
            self.strict_button,
            self.best_effort_button,
            self.validate_button,
            self.doctor_button,
            self.convert_button,
        ):
            widget.configure(state=state)
        self.name_style_box.configure(state="disabled" if busy else "readonly")
        if busy:
            self.progress.start(12)
        else:
            self.progress.stop()

    @staticmethod
    def _set_text(widget: tk.Text, content: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", content)
        widget.configure(state="disabled")

    def _close_window(self) -> None:
        if self._busy and not messagebox.askyesno(
            "转换仍在进行",
            "转换尚未结束，确定关闭窗口吗？",
            parent=self.master,
        ):
            return
        self.master.destroy()


def main() -> None:
    """启动 HDL-X 桌面应用。"""

    root = tk.Tk()
    HDLXApplication(root)
    root.mainloop()


if __name__ == "__main__":
    main()
