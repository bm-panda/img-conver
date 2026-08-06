"""
图片格式转换 - 支持多种图片格式互转
支持格式: PNG | JPEG | WEBP | BMP | GIF | ICO | TIFF
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List

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

DEFAULT_CONFIG = {
    "format": "png",
    "output_dir": "",
    "quality": 85,
}

TEMPLATE_PATH = Path(__file__).parent / "config.html"
CONFIG_PATH = Path(__file__).parent / "config.json"

# 模板里这个占位符会被替换为 `const APP_DATA = {...};`
APP_DATA_MARKER = "/*__APP_DATA__*/"


class ImageConverter:
    """图片格式转换器(基于 ImageMagick)"""

    def __init__(self, images: List[str], output_dir: str = "", quality: int = 85, output_format: str = "PNG"):
        """
        初始化转换器

        Args:
            images: 图片路径列表
            output_dir: 输出目录（为空则保存到原图目录）
            quality: 图片质量 (1-100)
            output_format: 输出格式 (PNG/JPG/WEBP等)
        """
        self.images = images
        self.output_dir = output_dir or ""
        self.quality = max(1, min(100, quality))  # 限制范围
        self.output_format = output_format.strip().lstrip(".").upper()

        if self.output_format.lower() not in ALL_WRITE_FORMATS:
            raise ValueError(f"不支持的格式：{self.output_format}，支持：{len(ALL_WRITE_FORMATS)} 种格式")

        self._magick = shutil.which("magick")
        if not self._magick:
            raise FileNotFoundError("未找到 ImageMagick（magick 命令），请确认已安装并在环境变量中")

        # 创建输出目录
        if self.output_dir:
            os.makedirs(self.output_dir, exist_ok=True)

    def _get_output_path(self, input_path: str) -> str:
        """生成输出文件路径"""
        stem = Path(input_path).stem
        ext = self.output_format.lower()
        if self.output_format == "JPEG":
            ext = "jpg"

        if self.output_dir:
            return os.path.join(self.output_dir, f"{stem}.{ext}")
        else:
            # 输出到原图目录
            parent = Path(input_path).parent
            return os.path.join(parent, f"{stem}_converted.{ext}")

    def _convert_single(self, image_path: str) -> tuple:
        """转换单张图片"""
        try:
            output_path = self._get_output_path(image_path)
            cmd = [self._magick, str(image_path)]
            if self.output_format in ("JPG", "JPEG", "WEBP"):
                cmd += ["-quality", str(self.quality)]
            if self.output_format in ("JPG", "JPEG"):
                cmd += ["-background", "white", "-alpha", "remove", "-alpha", "off"]
            cmd.append(output_path)

            proc = subprocess.run(
                cmd, capture_output=True, text=True, errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if proc.returncode != 0:
                return image_path, False, (proc.stderr or "转换失败").strip()
            return image_path, True, output_path

        except Exception as e:
            return image_path, False, str(e)

    def convert(self, max_workers: int = 4, progress_callback=None) -> dict:
        """
        批量转换图片

        Args:
            max_workers: 并发线程数
            progress_callback: 进度回调函数，接收 (当前进度, 总数)

        Returns:
            dict: 转换结果统计
        """
        total = len(self.images)
        results = {"success": [], "failed": [], "total": total}

        if total == 0:
            return results

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self._convert_single, path): path for path in self.images}

            for idx, future in enumerate(as_completed(futures), 1):
                path, success, info = future.result()
                if success:
                    results["success"].append((path, info))
                else:
                    results["failed"].append((path, info))

                if progress_callback:
                    progress_callback(idx, total)

        return results

    @staticmethod
    def get_file_size(path: str) -> str:
        """获取文件大小（人性化显示）"""
        size = os.path.getsize(path)
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


class App:
    """应用入口：配置窗口、配置读写、路径解析与 CLI 转换。"""

    def __init__(self, config_path: Path = CONFIG_PATH):
        self.config_path = config_path
        self.config = self.load_config()

    # ── 配置读写 ──
    def load_config(self) -> dict:
        """读取配置文件，不存在或格式错误则返回默认配置。"""
        config = dict(DEFAULT_CONFIG)
        if not self.config_path.exists():
            return config
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return {**config, **json.load(f)}
        except (json.JSONDecodeError, ValueError) as e:
            print(f"配置文件格式错误：{e}，使用默认配置")
            return config

    def _validate_saved(self, data):
        """对页面返回的配置做二次校验（镜像 HTML 里的 JS 规则）。"""
        if not isinstance(data, dict):
            raise ValueError("返回的数据格式无效")

        fmt = str(data.get("format", "") or "").strip().lstrip(".").lower()
        if fmt not in ALL_WRITE_FORMATS:
            raise ValueError(f"不支持的输出格式：{fmt}（支持 {len(ALL_WRITE_FORMATS)} 种）")
        data["format"] = fmt  # 归一化后落盘

        try:
            q = int(data.get("quality"))
        except (TypeError, ValueError):
            raise ValueError(f"无效的图片质量：{data.get('quality')}")
        if not 1 <= q <= 100:
            raise ValueError("图片质量必须在 1-100 之间")
        data["quality"] = q

    def _write_config(self, data) -> Path:
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return self.config_path

    # ── 配置窗口 ──
    def _render_html(self, config) -> str:
        """读取 HTML 模板并注入 APP_DATA（常量单一来源在 Python）。"""
        data = {
            "saved": config,
            "DEFAULTS": DEFAULT_CONFIG,
            "ALL_WRITE_FORMATS": ALL_WRITE_FORMATS,
        }
        payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        return html.replace(APP_DATA_MARKER, f"const APP_DATA = {payload};")

    def _spawn_webview(self, base_cmd, html):
        """先尝试 stdin 管道传入 HTML；失败则回退到临时 HTML 文件。

        注意 webview 的输入优先级：非空 stdin 优先于位置参数。
        """
        common = dict(
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            return subprocess.run([*base_cmd], input=html, **common)
        except (OSError, ValueError):
            fd, path = tempfile.mkstemp(suffix=".html", prefix="image-format-config-")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(html)
                return subprocess.run([*base_cmd, path], input="", **common)
            finally:
                try:
                    os.remove(path)
                except OSError:
                    pass

    def run_config_window(self) -> bool:
        """打开 HTML 配置窗口。返回 True 表示已保存配置，False 表示取消/出错。"""
        webview = shutil.which("webview-cli") or shutil.which("webview")
        if not webview:
            raise FileNotFoundError(
                "未找到 webview-cli，请确认已安装并加入 PATH\n"
                "https://github.com/just-be-dev/webview-cli"
            )

        html = self._render_html(self.config)
        base_cmd = [webview, "--title", "图片格式转换 - 配置窗口", "--width", "460", "--height", "640"]
        proc = self._spawn_webview(base_cmd, html)

        if proc.returncode == 0:
            try:
                data = json.loads(proc.stdout)
            except ValueError as e:
                print(f"配置窗口返回的数据无法解析：{e}")
                return False
            try:
                self._validate_saved(data)
            except (ValueError, TypeError) as e:
                print(f"配置校验失败：{e}")
                return False
            self._write_config(data)
            self.config = data
            return True
        elif proc.returncode == 2:
            return False  # 用户直接关窗 = 取消
        else:
            # reject(1) / 超时(3) / 用法错误(64)
            msg = (proc.stderr or "").strip()
            if msg:
                print(msg)
            return False

    # ── 文件路径 ──
    def get_path(self, param_path) -> List[str]:
        """从参数 JSON 中提取存在的目标图片路径。"""
        if not param_path or not Path(param_path).exists():
            return []
        with open(param_path, "r", encoding="utf-8") as f:
            params = json.load(f)
        raw = params.get("data", {}).get("target_paths", [])
        return [p for p in raw if Path(p).exists()]

    # ── CLI ──
    def run_cli(self, paths: list) -> None:
        """命令行转换：转换图片、打印结果、倒计时退出。"""
        print("-" * 50)
        print('图片格式转换')
        print("-" * 50)
        converter = ImageConverter(
            images=paths,
            output_dir=self.config["output_dir"],
            quality=int(self.config["quality"]),
            output_format=self.config["format"],
        )

        def show_progress(current, total):
            print(f"\r进度：{current}/{total} ({current / total * 100:.1f}%)", end="")

        result = converter.convert(max_workers=4, progress_callback=show_progress)
        print(f"\n\n✅ 成功：{len(result['success'])} 张")
        for path, output in result["success"]:
            print(f"   {os.path.basename(path)} → {os.path.basename(output)}")

        if result["failed"]:
            print(f"\n❌ 失败：{len(result['failed'])} 张")
            for path, error in result["failed"]:
                print(f"   {os.path.basename(path)}：{error}")

        # ── 倒计时 + 按键退出 ──
        print("\n" + "-" * 50)
        print("按任意键立即退出，或等待倒计时自动退出")

        # 倒计时
        for i in range(5, 0, -1):
            print(f"\r⏳ {i} 秒后自动退出... (按任意键退出)", end="")
            time.sleep(1)
        print("\r👋 已退出")
        sys.exit(0)

    def run(self) -> None:
        """应用入口：带参数走 CLI 转换，无参数打开配置窗口。"""
        param_path = sys.argv[1] if len(sys.argv) > 1 else None
        if param_path:
            paths = self.get_path(param_path)
            self.run_cli(paths)
        else:
            self.run_config_window()


def main():
    App().run()


if __name__ == "__main__":
    main()
