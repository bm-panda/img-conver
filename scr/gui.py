import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox
from ttkbootstrap import Style
import json
import os

# ==================== 格式定义 ====================
# 所有可写格式（扁平列表，按分类顺序，用于下拉框与验证）
ALL_WRITE_FORMATS = [
    # 最常用
    "jpg", "jpeg", "png", "webp", "gif", "bmp", "ico", "tiff", "tif",
    # 矢量/文档
    "svg", "pdf", "psd", "ai", "eps", "pdfa", "svgz",
    # 现代网络
    "avif", "jxl", "heic", "heif",
    # JPEG2000
    "jp2", "j2c", "j2k", "jpc", "jpm", "jpt",
    # 动画/序列
    "apng", "mng", "jng",
    # 游戏/3D
    "dds", "tga", "pcx", "pvr",
    # HDR/专业
    "exr", "hdr", "dpx", "cin", "fl32",
    # RAW相关
    "raw", "dng", "cr2", "nef", "arw", "orf",
    # PNM系列
    "pbm", "pgm", "ppm", "pnm",
    # X系列
    "xpm", "xbm",
    # Windows
    "cur", "wbmp",
    # 其他/特殊
    "dcx", "mtv", "sgi", "sun", "ras", "vicar", "viff", "xv",
    "fits", "fts", "pal", "uyvy", "yuv", "gray", "cmyk",
    "ps", "epdf", "epi", "epsf", "epsi", "eps2", "eps3",
    "ept", "ept2", "ept3", "miff", "mpc", "mvg", "palm",
    "pdb", "picon", "pocketmod", "psb", "ptif", "qoi",
    "sf3", "six", "sixel", "vda", "vst", "wpg",
    "bgr", "bgra", "bgro", "cmyka", "graya", "rgba",
    "rgbo", "rgb", "ycbcr", "ycbcra", "bayer", "bayera",
    "aai", "art", "avs", "cal", "cals", "cip", "group4",
    "fax", "g3", "g4", "hrz", "otb", "rle", "rgf",
    "ubrl", "ubrl6", "uil", "brf", "isobrl", "isobrl6",
]


# ==================== 占位文本输入框 ====================
class PlaceholderEntry(ttk.Entry):
    """输入框占位文本封装类"""

    def __init__(self, master, placeholder="", **kwargs):
        super().__init__(master, **kwargs)
        self.placeholder = placeholder
        self.default_fg = self.cget("foreground")

        self.insert(0, placeholder)
        self.config(foreground="#999")

        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)

    def _on_focus_in(self, event):
        if self.get() == self.placeholder:
            self.delete(0, tk.END)
            self.config(foreground=self.default_fg)

    def _on_focus_out(self, event):
        if self.get() == "":
            self.insert(0, self.placeholder)
            self.config(foreground="#999")

    def get_value(self):
        """获取实际输入的值（非占位文字）"""
        value = self.get()
        return "" if value == self.placeholder else value


class SearchableComboBox(ttk.Frame):
    """带搜索过滤的组合下拉框（搜索框是父容器相邻列中的兄弟组件，需调用方手动 grid）"""

    def __init__(self, master, values, placeholder="搜索...", **kwargs):
        super().__init__(master)

        self.all_values = values[:]
        self._selected_value = ""
        self._search_timer = None  # 用于防抖
        self.columnconfigure(0, weight=1)

        # 下拉框
        self.combobox = ttk.Combobox(
            self,
            values=values,
            font=("微软雅黑", 10),
            state="readonly",
            **kwargs
        )
        self.combobox.grid(row=0, column=0, sticky=tk.EW, padx=(0, 10))

        # 搜索框（父容器 master 的兄弟组件）
        self.search_entry = PlaceholderEntry(
            master,
            placeholder=placeholder,
            font=("微软雅黑", 10),
            width=8,
        )

        # 绑定事件
        self.search_entry.bind('<KeyRelease>', self._on_search)
        self.search_entry.bind('<FocusIn>', self._on_focus_in)
        self.combobox.bind('<<ComboboxSelected>>', self._on_select)

        # 存储选中的值
        self._selected_value = ""

    def _on_search(self, event):
        """搜索过滤（带防抖）"""
        # 取消之前的定时器
        if self._search_timer:
            self.after_cancel(self._search_timer)

        # 延迟 100ms 执行搜索，避免频繁刷新
        self._search_timer = self.after(100, self._do_search)

    def _do_search(self):
        """执行搜索"""
        keyword = self.search_entry.get()

        if keyword and keyword != self.search_entry.placeholder:
            # 过滤匹配项
            filtered = [f for f in self.all_values if keyword.lower() in f.lower()]
            self.combobox['values'] = filtered

            if filtered:
                # 自动选中第一个匹配项
                self.combobox.set(filtered[0])
                # 展开下拉列表
                self.combobox.event_generate('<Down>')
            else:
                # 无匹配项时清空
                self.combobox.set('')
        else:
            # 搜索框为空，恢复所有选项
            self.combobox['values'] = self.all_values
            # 恢复之前选中的值
            if self._selected_value and self._selected_value in self.all_values:
                self.combobox.set(self._selected_value)
            else:
                self.combobox.set('')

        self._search_timer = None

    def _on_focus_in(self, event):
        """获得焦点时清空占位文本并刷新列表"""
        if self.search_entry.get() == self.search_entry.placeholder:
            self.search_entry.delete(0, tk.END)
            self.search_entry.config(foreground=self.search_entry.default_fg)
        self.combobox['values'] = self.all_values
        if self._selected_value and self._selected_value in self.all_values:
            self.combobox.set(self._selected_value)

    def _on_focus_out(self, event):
        """失去焦点时清理"""
        # 如果搜索框为空或占位符，恢复选中值
        keyword = self.search_entry.get()
        if keyword == "" or keyword == self.search_entry.placeholder:
            self.combobox['values'] = self.all_values
            if self._selected_value and self._selected_value in self.all_values:
                self.combobox.set(self._selected_value)

    def _on_select(self, event):
        """选择后记录选中值并清空搜索框"""
        self._selected_value = self.combobox.get()
        # 清空搜索框
        self.search_entry.delete(0, tk.END)
        self.search_entry.insert(0, self.search_entry.placeholder)
        self.search_entry.config(foreground="#999")
        # 恢复所有选项
        self.combobox['values'] = self.all_values
        self.combobox.set(self._selected_value)

    def get(self):
        """获取选中的值"""
        return self.combobox.get()

    def set(self, value):
        """设置值"""
        if value in self.all_values:
            self.combobox.set(value)
            self._selected_value = value

    def get_all_values(self):
        """获取所有选项"""
        return self.all_values[:]

    def set_values(self, values):
        """设置选项列表"""
        self.all_values = values[:]
        self.combobox['values'] = values

    def bind_select(self, callback):
        """绑定选择事件"""
        self.combobox.bind('<<ComboboxSelected>>', lambda e: callback(self.get()))


class App(tk.Tk):
    def __init__(self, config=None):
        super().__init__()

        # 默认配置
        default_config = {
            "format": "webp",
            "output_dir": "",
            "quality": 85
        }

        # 合并配置
        if config:
            self.config = {**default_config, **config}
        else:
            self.config = default_config

        self._init_ui()
        self.center_window()

    def _init_ui(self):
        self.title("图片格式转换 - 配置窗口")
        self.style = Style(theme="cosmo")

        main = ttk.Frame(self, padding=20)
        main.pack(fill=tk.BOTH, expand=True)

        # ── 配置列权重 ──
        main.columnconfigure(0, weight=0)
        main.columnconfigure(1, weight=1)
        main.columnconfigure(2, weight=0)

        # ── 第1行：输出格式 ──
        ttk.Label(main, text="输出格式：", font=("微软雅黑", 10)).grid(
            row=0, column=0, sticky=tk.W, padx=(0, 10), pady=6
        )
        self.format_selector = SearchableComboBox(
            main,
            values=ALL_WRITE_FORMATS,
            placeholder="搜索后缀名..."
        )
        self.format_selector.grid(row=0, column=1, sticky=tk.EW, pady=6)
        self.format_selector.search_entry.grid(row=0, column=2, sticky=tk.EW, pady=6)

        # 设置默认值
        if self.config["format"] in ALL_WRITE_FORMATS:
            self.format_selector.set(self.config["format"])

        # ── 第2行：输出目录 ──
        ttk.Label(main, text="输出目录：", font=("微软雅黑", 10)).grid(
            row=1, column=0, sticky=tk.W, padx=(0, 10), pady=6
        )

        default_dir = self.config["output_dir"] if self.config["output_dir"] else "留空则输出到原图所在目录"
        self.dir_entry = PlaceholderEntry(
            main,
            placeholder=default_dir,
            font=("微软雅黑", 10),
        )
        self.dir_entry.grid(row=1, column=1, sticky=tk.EW, pady=6, padx=(0, 10))

        ttk.Button(main, text="选择目录", command=self.select_directory).grid(
            row=1, column=2, sticky=tk.E, pady=6
        )

        # ── 第3行：图片质量 ──
        ttk.Label(main, text="图片质量：", font=("微软雅黑", 10)).grid(
            row=2, column=0, sticky=tk.W, padx=(0, 10), pady=6
        )

        quality = self.config["quality"]
        self.quality_var = tk.IntVar(value=int(quality))
        quality_scale = ttk.Scale(
            main,
            from_=0,
            to=100,
            variable=self.quality_var
        )
        quality_scale.grid(row=2, column=1, sticky=tk.EW, pady=6, padx=(0, 10))

        self.value_label = ttk.Label(main, text=f"{quality}%", font=("微软雅黑", 10), width=5)
        self.value_label.grid(row=2, column=2, sticky=tk.W, pady=6)

        def update_label(*args):
            self.value_label.config(text=f"{self.quality_var.get()}%")

        self.quality_var.trace_add('write', update_label)

        # ── 第4行：保存按钮 ──
        ttk.Button(main, text="保存配置", command=self._save_config).grid(
            row=3, column=0, columnspan=3, sticky=tk.EW, pady=(15, 5)
        )

        # ── 提示区域 ──
        tip_frame = ttk.LabelFrame(
            main,
            text="💡 使用说明",
            padding=(10, 8),
        )
        tip_frame.grid(row=4, column=0, columnspan=3, sticky=tk.EW, pady=(10, 0))

        ttk.Label(
            tip_frame,
            text="📌 保存配置后，鼠标选中图片 → 右键菜单选择「图片格式转换」",
            font=("微软雅黑", 9),
            foreground="#009a29"
        ).pack(anchor=tk.W, pady=(0, 2))

        ttk.Label(
            tip_frame,
            text="⚠️ 需要通过「不忙脚本盒子」安装此脚本才能使用右键功能",
            font=("微软雅黑", 8),
            foreground="#909399"
        ).pack(anchor=tk.W, pady=(0, 0))

    def center_window(self):
        """居中显示窗口"""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        screenwidth = self.winfo_screenwidth()
        screenheight = self.winfo_screenheight()
        x = (screenwidth - width) // 2
        y = (screenheight - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

        # 图标文件存在则设置
        ico_path = Path(__file__).parent.parent / "imgs" / "img.ico"
        if Path(ico_path).exists():
            try:
                self.iconbitmap(ico_path)
            except:
                pass

    def _save_config(self):
        """保存配置"""
        fmt = self.format_selector.get().strip().lstrip(".").lower()

        # 检查是否选择了分类标题
        if fmt.startswith("───") or fmt == "":
            messagebox.showwarning("格式无效", "请选择有效的输出格式！")
            return

        # 验证格式是否支持
        if fmt not in ALL_WRITE_FORMATS:
            messagebox.showwarning(
                "格式不支持",
                f"「{fmt}」不是受支持的输出格式\n\n"
                f"支持的格式列表：\n{', '.join(ALL_WRITE_FORMATS[:20])}..."
            )
            return

        output_dir = self.dir_entry.get_value()

        config = {
            "format": fmt,
            "output_dir": output_dir,
            "quality": self.quality_var.get(),
        }
        config_path = Path(__file__).parent.parent / "config.json"
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("成功", "✅ 配置已保存成功！")
            self.after(500, self.destroy)
        except Exception as e:
            messagebox.showerror("错误", f"保存配置失败：{str(e)}")

    def select_directory(self):
        """选择输出目录"""
        directory = filedialog.askdirectory(title="选择输出目录")
        if directory:
            self.dir_entry.delete(0, tk.END)
            self.dir_entry.insert(0, directory)
            self.dir_entry.config(foreground="#000")


# ==================== 启动入口 ====================
def load_config():
    """加载配置文件"""
    config = {"format": "webp", "output_dir": "", "quality": 85}

    if os.path.exists("config.json"):
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                saved = json.load(f)
                config.update(saved)
        except:
            pass

    return config


if __name__ == "__main__":
    config = load_config()
    app = App(config)
    app.mainloop()
