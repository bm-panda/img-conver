"""
图片格式转换 - 支持多种图片格式互转
支持格式: PNG | JPEG | WEBP | BMP | GIF | ICO | TIFF
"""
import sys
import json
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from ttkbootstrap import Style
from pathlib import Path
from PIL import Image


# ── 支持的格式 ──────────────────────────────────────────────
SUPPORTED_FORMATS = ["PNG", "JPEG", "WEBP", "BMP", "GIF", "ICO", "TIFF"]

FORMAT_EXT_MAP = {
    "PNG": ".png",
    "JPEG": ".jpg",
    "WEBP": ".webp",
    "BMP": ".bmp",
    "GIF": ".gif",
    "ICO": ".ico",
    "TIFF": ".tiff",
}


IMAGE_FILTERS = [
    ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".ico", ".tiff", ".tif",
]


class App(tk.Tk):
    """图片格式转换主窗口"""

    def __init__(self, initial_files=None):
        super().__init__()
        self.title("图片格式转换")
        self.geometry("720x520")
        self.minsize(600, 440)

        # 主题
        self.style = Style(theme="flatly")

        # ── 状态 ──
        self.file_list: list[str] = list(initial_files or [])
        self.output_dir = tk.StringVar(value="")
        self.output_format = tk.StringVar(value="PNG")

        # ── 界面 ──
        self._build_ui()
        self._refresh_file_list()

    # ──────────────── UI 构建 ────────────────

    def _build_ui(self):
        main = ttk.Frame(self, padding=15)
        main.pack(fill=tk.BOTH, expand=True)

        # 标题
        ttk.Label(main, text="图片格式转换",
                  font=("微软雅黑", 16, "bold")).pack(pady=(0, 10))

        # ── 左右分栏 ──
        content = ttk.Frame(main)
        content.pack(fill=tk.BOTH, expand=True)

        # ===== 左侧：文件列表 =====
        left = ttk.LabelFrame(content, text="选择图片", padding=8)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        btn_row = ttk.Frame(left)
        btn_row.pack(fill=tk.X, pady=(0, 5))
        ttk.Button(btn_row, text="添加图片",
                   command=self._add_files).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="清空列表",
                   command=self._clear_files).pack(side=tk.LEFT, padx=2)

        lb_frame = ttk.Frame(left)
        lb_frame.pack(fill=tk.BOTH, expand=True)

        self.file_lb = tk.Listbox(lb_frame, font=("微软雅黑", 9),
                                  selectbackground="#cce5ff")
        sb = ttk.Scrollbar(lb_frame, orient=tk.VERTICAL,
                           command=self.file_lb.yview)
        self.file_lb.config(yscrollcommand=sb.set)
        self.file_lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        self.count_label = ttk.Label(left, text="共 0 个文件",
                                     font=("微软雅黑", 9))
        self.count_label.pack(anchor=tk.W, pady=(5, 0))

        # ===== 右侧：设置面板 =====
        right = ttk.LabelFrame(content, text="转换设置", padding=10)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))

        # 输出格式
        ttk.Label(right, text="输出格式：",
                  font=("微软雅黑", 10)).pack(anchor=tk.W, pady=(5, 2))
        fmt_combo = ttk.Combobox(right, textvariable=self.output_format,
                                 values=SUPPORTED_FORMATS, state="readonly",
                                 width=16, font=("微软雅黑", 10))
        fmt_combo.pack(anchor=tk.W, fill=tk.X, pady=(0, 12))
        fmt_combo.current(0)

        # 输出目录
        ttk.Label(right, text="输出位置：",
                  font=("微软雅黑", 10)).pack(anchor=tk.W, pady=(5, 2))
        self.dir_label = ttk.Label(right,
                                   text="（不指定则输出到源文件所在目录）",
                                   font=("微软雅黑", 9), foreground="#888")
        self.dir_label.pack(anchor=tk.W, pady=(0, 5))

        dir_btn_frame = ttk.Frame(right)
        dir_btn_frame.pack(anchor=tk.W, fill=tk.X, pady=(0, 12))
        ttk.Button(dir_btn_frame, text="选择目录...",
                   command=self._select_output_dir,
                   bootstyle="info-outline").pack(side=tk.LEFT)
        ttk.Button(dir_btn_frame, text="清除",
                   command=self._clear_output_dir,
                   bootstyle="secondary-link").pack(side=tk.LEFT, padx=5)

        # 间隔占位
        ttk.Label(right, text="").pack(fill=tk.BOTH, expand=True)

        # 转换按钮
        self.convert_btn = ttk.Button(right, text="开始转换",
                                      command=self._on_convert_clicked,
                                      bootstyle="success", width=18,
                                      padding=(5, 8))
        self.convert_btn.pack(pady=(5, 5))

        # ── 底部状态栏 ──
        status_bar = ttk.Frame(main)
        status_bar.pack(fill=tk.X, pady=(8, 0))

        self.status_var = tk.StringVar(value="就绪")
        self.status_lbl = ttk.Label(status_bar, textvariable=self.status_var,
                                    font=("微软雅黑", 9), foreground="#555")
        self.status_lbl.pack(side=tk.LEFT)

        self.progress = ttk.Progressbar(status_bar, mode="indeterminate",
                                        length=180)

    # ──────────────── 文件列表操作 ────────────────

    def _add_files(self):
        files = filedialog.askopenfilenames(
            title="选择要转换的图片",
            filetypes=[
                ("图片文件", "*.png *.jpg *.jpeg *.webp *.bmp *.gif *.ico *.tiff *.tif"),
                ("所有文件", "*.*"),
            ],
        )
        if not files:
            return
        existing = set(self.file_list)
        for f in files:
            if f not in existing:
                self.file_list.append(f)
                existing.add(f)
        self._refresh_file_list()

    def _clear_files(self):
        self.file_list.clear()
        self._refresh_file_list()

    def _refresh_file_list(self):
        self.file_lb.delete(0, tk.END)
        for f in self.file_list:
            self.file_lb.insert(tk.END, f"  {Path(f).name}")
        self.count_label.config(text=f"共 {len(self.file_list)} 个文件")

    # ──────────────── 目录操作 ────────────────

    def _select_output_dir(self):
        d = filedialog.askdirectory(title="选择输出目录")
        if d:
            self.output_dir.set(d)
            self.dir_label.config(text=d, foreground="#333")

    def _clear_output_dir(self):
        self.output_dir.set("")
        self.dir_label.config(text="（不指定则输出到源文件所在目录）",
                              foreground="#888")

    # ──────────────── 转换逻辑 ────────────────

    def _on_convert_clicked(self):
        """用户点击转换按钮时的入口（启动线程防卡界面）"""
        if not self.file_list:
            messagebox.showwarning("提示", "请先添加要转换的图片文件")
            return

        # 禁用按钮，启动进度条
        self.convert_btn.config(state=tk.DISABLED, text="转换中…")
        self.progress.pack(side=tk.RIGHT)
        self.progress.start(10)
        self.status_var.set("正在转换中，请稍候…")
        self.status_lbl.config(foreground="#555")

        # 在后台线程执行转换
        thread = threading.Thread(target=self._convert, daemon=True)
        thread.start()

    def _convert(self):
        """执行图片转换（在线程中运行）"""
        fmt = self.output_format.get()
        ext = FORMAT_EXT_MAP[fmt]
        out_dir_str = self.output_dir.get().strip()

        results = {"success": [], "failed": []}

        for file_path in self.file_list:
            try:
                src = Path(file_path)
                dst_dir = Path(out_dir_str) if out_dir_str else src.parent
                dst_dir.mkdir(parents=True, exist_ok=True)

                dst_path = dst_dir / (src.stem + ext)

                # 防重名
                counter = 1
                while dst_path.exists():
                    dst_path = dst_dir / f"{src.stem}_{counter}{ext}"
                    counter += 1

                img = Image.open(src)

                # 格式特殊处理
                if fmt == "JPEG" and img.mode in ("RGBA", "LA", "P"):
                    bg = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "P":
                        img = img.convert("RGBA")
                    bg.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                    img = bg
                elif fmt == "ICO":
                    if img.size[0] > 256 or img.size[1] > 256:
                        img.thumbnail((256, 256), Image.LANCZOS)

                img.save(dst_path)
                img.close()
                results["success"].append(str(dst_path))

            except Exception as e:
                results["failed"].append({"file": file_path, "error": str(e)})

        # 回到主线程更新 UI
        self.after(0, self._on_convert_done, results)

    def _on_convert_done(self, results):
        """转换完成后的 UI 更新（主线程）"""
        self.progress.stop()
        self.progress.pack_forget()
        self.convert_btn.config(state=tk.NORMAL, text="开始转换")

        ok = len(results["success"])
        ng = len(results["failed"])

        if ng == 0:
            self.status_var.set(f"✓ 转换完成！成功 {ok} 个文件")
            self.status_lbl.config(foreground="#28a745")
            msg = f"转换完成！\n\n成功转换 {ok} 个文件"
        else:
            self.status_var.set(f"转换完成：成功 {ok} 个，失败 {ng} 个")
            self.status_lbl.config(foreground="#dc3545")
            details = "\n".join(
                f"• {Path(f['file']).name}：{f['error']}"
                for f in results["failed"]
            )
            msg = f"转换完成！\n\n成功：{ok} 个\n失败：{ng} 个\n\n{details}"

        messagebox.showinfo("转换结果", msg)


# ──────────────── 入口 ────────────────

def main():
    param_path = sys.argv[1] if len(sys.argv) > 1 else None
    initial_files = []

    if param_path and Path(param_path).exists():
        with open(param_path, "r", encoding="utf-8") as f:
            params = json.load(f)
        raw = params.get("data", {}).get("target_paths", [])
        initial_files = [p for p in raw if Path(p).exists()]

    app = App(initial_files=initial_files)
    app.mainloop()


if __name__ == "__main__":
    main()
