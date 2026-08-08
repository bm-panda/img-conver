"""
图片格式转换 - 支持多种图片格式互转
支持格式: PNG | JPEG | WEBP | BMP | GIF | ICO | TIFF 等 200+ 种
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import List

# ── 路径与模板 ──
BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"
CONFIG_TEMPLATE = BASE_DIR / "config.html"
APP_DATA_MARKER = "/*__APP_DATA__*/"

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

# 右键可选的图片扩展名（与 bm-scripts-box-rc.toml 的 filters 一致；
# ALL_WRITE_FORMATS 派生 + 仅可输入的相机/文档格式补充）
IMAGE_EXTS = {"." + f for f in ALL_WRITE_FORMATS} | {
    ".cr3", ".rw2", ".xcf", ".pict", ".ani", ".rla", ".sct", ".pix", ".al",
    ".ipl", ".x3f", ".xps", ".fff", ".mos", ".mef", ".mrw", ".mdc",
    ".dcm", ".dicom", ".ora",
}


class ImageConverter:
    """图片格式转换器（基于 ImageMagick），承载通用 subprocess 执行，只产数据。"""

    @staticmethod
    def _run(cmd, **kw):
        """执行命令，默认隐藏控制台窗口、按 UTF-8 容错解码。"""
        kw.setdefault("creationflags", getattr(subprocess, "CREATE_NO_WINDOW", 0))
        kw.setdefault("encoding", "utf-8")
        return subprocess.run(cmd, text=True, errors="replace", **kw)

    @staticmethod
    def _require_binaries():
        """校验 magick，缺则直接报错（供 Cli 开局预检）。"""
        if not shutil.which("magick"):
            raise FileNotFoundError(
                "未找到 ImageMagick（magick 命令），请安装并加入环境变量 PATH（https://imagemagick.org/script/download.php）")

    def __init__(self, images, config):
        """images: 图片文件路径列表；config: 配置 dict（见 DEFAULT_CONFIG）。"""
        self.images = [i for i in images if Path(i).exists()]
        c = config

        self.output_dir = str(c.get("output_dir") or "").strip()
        self.output_format = str(c.get("format") or "png").strip().lstrip(".").upper()
        if self.output_format.lower() not in ALL_WRITE_FORMATS:
            raise ValueError(f"不支持的格式：{self.output_format}，支持：{len(ALL_WRITE_FORMATS)} 种格式")

        self.quality = max(1, min(100, int(c.get("quality", 85))))

        self._require_binaries()
        self._magick = shutil.which("magick")

        if self.output_dir:
            os.makedirs(self.output_dir, exist_ok=True)

    def _get_output_path(self, input_path: str) -> str:
        """生成输出文件路径；输出到原图目录时加 _converted 后缀避免覆盖原文件"""
        stem = Path(input_path).stem
        ext = self.output_format.lower()
        if self.output_format == "JPEG":
            ext = "jpg"

        if self.output_dir:
            return os.path.join(self.output_dir, f"{stem}.{ext}")
        else:
            parent = Path(input_path).parent
            return os.path.join(parent, f"{stem}_converted.{ext}")

    def _convert_single(self, image_path: str, on_start=None) -> tuple:
        """转换单张图片，返回 (路径, 状态, 信息)，状态: success/failed。"""
        try:
            output_path = self._get_output_path(image_path)

            if on_start:
                on_start(image_path)

            cmd = [self._magick, str(image_path)]
            if self.output_format in ("JPG", "JPEG", "WEBP"):
                cmd += ["-quality", str(self.quality)]
            if self.output_format in ("JPG", "JPEG"):
                # 透明通道 JPEG 不支持，自动铺白底
                cmd += ["-background", "white", "-alpha", "remove", "-alpha", "off"]
            cmd.append(output_path)

            proc = self._run(cmd, capture_output=True)
            if proc.returncode != 0:
                return image_path, "failed", (proc.stderr or "转换失败").strip()
            return image_path, "success", output_path

        except Exception as e:
            return image_path, "failed", str(e)

    def convert(self, on_start=None, on_done=None) -> dict:
        """顺序转换全部图片，回调供 Cli 展示；返回分组结果 dict。"""
        results = {"success": [], "failed": [], "total": len(self.images)}

        for path in self.images:
            path, status, info = self._convert_single(path, on_start=on_start)
            if status == "success":
                results["success"].append((path, info))
            else:
                results["failed"].append((path, info))
            if on_done:
                on_done(path, status, info)

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


class Gui:
    """webview-cli 配置窗口（含配置的读写与校验）。"""

    @staticmethod
    def _render(data):
        """读取 HTML 模板并注入 APP_DATA（常量单一来源在 Python）。"""
        payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
        html = CONFIG_TEMPLATE.read_text(encoding="utf-8")
        return html.replace(APP_DATA_MARKER, f"const APP_DATA = {payload};")

    @staticmethod
    def _webview_bin():
        webview = shutil.which("webview-cli") or shutil.which("webview")
        if not webview:
            raise FileNotFoundError(
                "未找到 webview-cli，请确认已安装并加入 PATH\n"
                "https://github.com/just-be-dev/webview-cli"
            )
        return webview

    @staticmethod
    def _validate(data):
        """校验配置窗口返回的数据（镜像 HTML 里的 JS 规则），返回规范化后的 dict。"""
        if not isinstance(data, dict):
            raise ValueError("返回的数据格式无效")

        fmt = str(data.get("format") or "").strip().lstrip(".").lower()
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

        data["output_dir"] = str(data.get("output_dir") or "").strip()
        # 补齐默认字段，保证 config.json 全字段、下游解析安全
        for k, v in DEFAULT_CONFIG.items():
            if k not in data:
                data[k] = v
        return data

    @staticmethod
    def load_config():
        """读取配置；缺失/损坏/非法返回 None（触发首次引导）。"""
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        return data if data.get("format") in ALL_WRITE_FORMATS else None

    @staticmethod
    def save_config(data):
        CONFIG_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def ask(self):
        """打开配置窗口，返回校验后的配置 dict；取消/出错返回 None。"""
        webview = self._webview_bin()
        data = {"saved": self.load_config() or {},
                "DEFAULTS": DEFAULT_CONFIG,
                "ALL_WRITE_FORMATS": ALL_WRITE_FORMATS}
        html = self._render(data)
        cmd = [webview, "--title", "图片格式转换 - 配置窗口", "--width", "460", "--height", "640"]
        try:
            proc = ImageConverter._run(cmd, input=html, capture_output=True)
        except (OSError, ValueError):
            # stdin 管道不可用时回退到临时 HTML 文件
            fd, path = tempfile.mkstemp(suffix=".html", prefix="image-format-webview-")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(html)
                proc = ImageConverter._run(cmd + [path], input="", capture_output=True)
            finally:
                try:
                    os.remove(path)
                except OSError:
                    pass
        if proc.returncode:
            if proc.returncode != 2 and (proc.stderr or "").strip():
                print((proc.stderr or "").strip())
            return None  # 取消(2) / 出错
        try:
            payload = json.loads(proc.stdout)
        except ValueError:
            print("配置窗口返回的数据无法解析")
            return None
        try:
            return self._validate(payload)
        except (ValueError, TypeError) as e:
            print(f"配置校验失败：{e}")
            return None


class Cli:
    """批处理命令行流程（含盒子参数解析与输出编码修复）。"""

    @staticmethod
    def _fix_encoding():
        # 统一输出编码，避免 GBK 控制台下 emoji/中文报错（盒子环境已设 PYTHONUTF8=1）
        for _s in (sys.stdout, sys.stderr):
            try:
                _s.reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, ValueError):
                pass

    @staticmethod
    def _dw(text):
        """近似显示宽度：CJK/全角/emoji 计 2，其余计 1（横幅自适应宽度用）。"""
        return sum(2 if ord(ch) > 0x2E7F else 1 for ch in text)

    @staticmethod
    def _version():
        try:
            for line in (BASE_DIR / "bm-scripts-box-rc.toml").read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("version"):
                    return line.split("=", 1)[1].strip().strip('"')
        except OSError:
            pass
        return ""

    @staticmethod
    def _title():
        v = Cli._version()
        return f"🖼️ 图片格式转换{(' v' + v) if v else ''} · 200+ 格式互转"

    @staticmethod
    def _banner(text):
        w = Cli._dw(text) + 4
        bar = "─" * w
        print("┌" + bar + "┐")
        print("│  " + text + "  │")
        print("└" + bar + "┘")

    @staticmethod
    def _section(title):
        print(f"── {title} " + "─" * 22)

    @staticmethod
    def get_path(param_path):
        """解析盒子传入的 JSON 参数文件，返回存在的图片路径列表。"""
        if not (param_path and Path(param_path).exists()):
            return []
        try:
            with open(param_path, "r", encoding="utf-8") as f:
                params = json.load(f)
        except (OSError, json.JSONDecodeError):
            return []
        raw = params.get("data", {}).get("target_paths", [])
        return [p for p in raw if Path(p).exists()]

    def _config_summary(self, config):
        """转换参数摘要（配置分节说明用，两行）。"""
        line1 = f"🖼️ 输出 {config.get('format')} · 质量 {config.get('quality')}"
        out = config.get("output_dir") or "原图所在目录"
        return f"{line1}\n  📁 输出目录 {out}"

    def run(self, paths):
        """批处理主流程：扫描 → 配置 → 处理 → 结果 → 倒计时退出。"""
        Cli._banner(Cli._title())

        images, skipped = [], []
        for p in paths:
            if Path(p).suffix.lower() in IMAGE_EXTS:
                images.append(p)
            else:
                skipped.append(p)
        if skipped:
            self._section("扫描")
            for p in skipped:
                print(f"  ⏭️ 忽略非图片: {Path(p).name}")

        if not images:
            print("  ❌ 未选择有效的图片文件")
            self._exit()
            return

        self._section("配置")
        config = Gui.load_config()
        if config is None:
            print("  📋 首次使用，请配置转换参数...")
            config = Gui().ask()
            if config is None:
                print("  ❌ 未获取到配置，已取消转换")
                self._exit()
                return
            Gui.save_config(config)
            print("  ✅ 配置已保存")
        else:
            print("  💾 使用已保存的配置")
        print(f"  {self._config_summary(config)}")

        self._section("处理")
        total = len(images)
        started = [0]

        def on_start(path):
            started[0] += 1
            print(f"  ▶ ({started[0]}/{total}) 正在转换: {Path(path).name}")

        def on_done(path, status, info):
            name = Path(path).name
            if status == "success":
                size = ImageConverter.get_file_size(info)
                print(f"  ✅ {name} → {Path(info).name}（{size}）")
            else:
                print(f"  ❌ {name}  {(info or '未知错误').strip().splitlines()[0]}")

        converter = ImageConverter(images, config)
        result = converter.convert(on_start=on_start, on_done=on_done)

        self._section("结果")
        parts = [f"✅ 成功 {len(result['success'])} 张"]
        if result["failed"]:
            parts.append(f"❌ 失败 {len(result['failed'])} 张")
        print("  " + " · ".join(parts))
        self._exit()

    @staticmethod
    def _exit():
        width, total = 10, 5
        for i in range(total, 0, -1):
            filled = round(width * (total - i + 1) / total)
            bar = "█" * filled + "░" * (width - filled)
            print(f"\r  ⏳ {i}s {bar}  按任意键立即退出", end="")
            time.sleep(1)
        print("\r" + " " * 60, end="\r")
        print("  👋 已退出")
        sys.exit(0)


def main():
    Cli._fix_encoding()                      # 先修编码，再打印任何东西
    param_path = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        if param_path:                        # 盒子传入 JSON 参数 → 批处理
            paths = Cli.get_path(param_path)
            if not paths:
                print("未获取到有效的文件路径")
                time.sleep(2)
            else:
                Cli().run(paths)
        else:                                 # 无参 → 打开配置窗口
            Cli._banner(Cli._title())
            config = Gui().ask()
            if config is not None:
                Gui.save_config(config)
            print(("  ✅ 配置已保存" if config else "  未保存配置") + "\n")
            time.sleep(2)
    except FileNotFoundError as e:            # 缺二进制/webview → 中文报错，停留 3 秒
        print(f"❌ {e}")
        time.sleep(3)


if __name__ == "__main__":
    main()
