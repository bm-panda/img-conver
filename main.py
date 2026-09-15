"""
图片格式转换 - 支持多种图片格式互转
支持格式: PNG | JPEG | WEBP | BMP | GIF | ICO | TIFF 等 200+ 种

启动方式：由不忙脚本盒子渲染 params_form 启动参数窗口收集参数，
脚本读取 JSON 参数文件（data/params）直接执行转换。
三种模式：
  - manual    手动触发（右键/快捷键/卡片）：控制台显示转换进度 + 倒计时退出
  - scheduled 定时任务：与控制台模式一致，打印进度 + 倒计时退出
  - node      被其他脚本联动调用：无头转换，结果以信封写入 output_json
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Tuple

# ============ 常量 ============
BASE_DIR = Path(__file__).resolve().parent
QUALITY_MIN, QUALITY_MAX = 1, 100

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

# 右键可选的图片扩展名（ALL_WRITE_FORMATS 派生 + 仅可输入的相机/文档格式补充；
# 与 bm-scripts-box-rc.toml 的 filters 一致）
IMAGE_EXTS = {"." + f for f in ALL_WRITE_FORMATS} | {
    ".cr3", ".rw2", ".xcf", ".pict", ".ani", ".rla", ".sct", ".pix", ".al",
    ".ipl", ".x3f", ".xps", ".fff", ".mos", ".mef", ".mrw", ".mdc",
    ".dcm", ".dicom", ".ora",
}


# ============ 基础设施工具（通用、无状态、可独立单测） ============
def run_cmd(cmd: List[str], **kwargs) -> subprocess.CompletedProcess:
    """统一命令执行，默认隐藏窗口、UTF-8 容错解码。"""
    kwargs.setdefault("creationflags", getattr(subprocess, "CREATE_NO_WINDOW", 0))
    kwargs.setdefault("encoding", "utf-8")
    kwargs.setdefault("text", True)
    kwargs.setdefault("errors", "replace")
    return subprocess.run(cmd, **kwargs)


def get_script_version() -> str:
    """读取脚本版本号（单一来源 bm-scripts-box-rc.toml，不硬编码）。"""
    try:
        for line in (BASE_DIR / "bm-scripts-box-rc.toml").read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("version"):
                return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return ""


def title() -> str:
    v = get_script_version()
    return f" 🖼️ 图片格式转换{(' v' + v) if v else ''} · 200+ 格式互转"


def print_banner(text: str) -> None:
    """打印装饰标题（按显示宽度自适应，纯 Unicode 零依赖）。"""
    width = sum(2 if ord(c) > 0x2E7F else 1 for c in text) + 4
    bar = "─" * width
    print(f"┌{bar}┐\n│  {text}  │\n└{bar}┘")


def print_section(title_: str) -> None:
    print(f"── {title_} " + "─" * 22)


def countdown_exit(seconds: int = 5) -> None:
    """批量处理结束后的倒计时退出：进度条实时刷新，按任意键立即退出。"""
    width = 10
    try:
        import msvcrt
        has_key = True
    except ImportError:
        has_key = False
    for i in range(seconds, 0, -1):
        if has_key and msvcrt.kbhit():
            break
        filled = round(width * (seconds - i + 1) / seconds)
        bar = "█" * filled + "░" * (width - filled)
        print(f"\r  ⏳ {i}s {bar}  按任意键立即退出", end="", flush=True)
        time.sleep(1)
    print("\r" + " " * 60 + "\r  👋 已退出", flush=True)
    sys.exit(0)


def pause_exit(message: str = "按任意键退出") -> None:
    """无参引导模式：暂停等待用户按键后退出（不倒计时）。"""
    try:
        import msvcrt
        print(f"\n  {message}...", end="", flush=True)
        msvcrt.getch()
    except ImportError:
        input(f"\n  {message}...")
    print("\r  👋 已退出")
    sys.exit(0)


def _read_payload(param_path: str):
    """读取盒子传入的参数 JSON，返回 dict；解析失败返回 None。"""
    try:
        with open(param_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


# ============ 图片转换引擎 ============
class ImageConverter:
    """图片格式转换器（基于 ImageMagick），只产数据、不掺展示。"""

    def __init__(self, config: dict):
        c = {**DEFAULT_CONFIG, **(config or {})}
        self.output_dir = str(c.get("output_dir") or "").strip()
        self.format = str(c.get("format") or "png").strip().lstrip(".").lower()
        if self.format not in ALL_WRITE_FORMATS:
            raise ValueError(f"不支持的格式：{self.format}，支持 {len(ALL_WRITE_FORMATS)} 种格式")
        try:
            self.quality = max(QUALITY_MIN, min(QUALITY_MAX, int(c.get("quality", 85))))
        except (TypeError, ValueError):
            self.quality = DEFAULT_CONFIG["quality"]
        self._magick = shutil.which("magick")
        if not self._magick:
            raise FileNotFoundError(
                "未找到 ImageMagick（magick）命令，请安装并加入环境变量 PATH"
                "（https://imagemagick.org/script/download.php）")
        if self.output_dir:
            os.makedirs(self.output_dir, exist_ok=True)

    @staticmethod
    def _ext_for(fmt: str) -> str:
        """输出扩展名：jpeg 归一为 jpg，其余原样。"""
        return "jpg" if fmt == "jpeg" else fmt

    def output_path(self, input_path: str) -> str:
        """输出路径；输出到原图所在目录时加 _converted 后缀避免覆盖原文件。"""
        stem = Path(input_path).stem
        ext = self._ext_for(self.format)
        if self.output_dir:
            return os.path.join(self.output_dir, f"{stem}.{ext}")
        return os.path.join(Path(input_path).parent, f"{stem}_converted.{ext}")

    def convert_one(self, image_path: str) -> Tuple[bool, str, str]:
        """转换单张，返回 (ok, detail, output_path)；失败 detail 为错误。"""
        output = self.output_path(image_path)
        cmd = [self._magick, str(image_path)]
        if self.format in ("jpg", "jpeg", "webp"):
            cmd += ["-quality", str(self.quality)]
        if self.format in ("jpg", "jpeg"):
            # 透明通道 JPEG 不支持，自动铺白底
            cmd += ["-background", "white", "-alpha", "remove", "-alpha", "off"]
        cmd.append(output)
        try:
            proc = run_cmd(cmd, capture_output=True)
        except OSError as e:
            return False, str(e), ""
        if proc.returncode != 0:
            return False, (proc.stderr or "转换失败").strip(), ""
        return True, "", output

    @staticmethod
    def get_file_size(path: str) -> str:
        """获取文件大小（人性化显示）。"""
        size = os.path.getsize(path)
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


# ============ 主流程 ============
class App:
    """应用主流程（读取盒子注入的参数 → 转换 → 展示 / 写信封）。"""

    @staticmethod
    def _resolve_params(payload: dict) -> dict:
        """从 params 段取运行参数，缺省回退 DEFAULT_CONFIG。"""
        params = payload.get("params") or {}

        def pval(name, default):
            v = params.get(name)
            if v in (None, ""):
                return default
            return v

        return {
            "format": str(pval("format", DEFAULT_CONFIG["format"])),
            "quality": pval("quality", DEFAULT_CONFIG["quality"]),
            "output_dir": str(pval("output_dir", DEFAULT_CONFIG["output_dir"]) or ""),
        }

    @staticmethod
    def _collect_images(payload: dict) -> List[str]:
        """从 data 段取目标图片（过滤扩展名 + 存在性）。"""
        data = payload.get("data") or {}
        return [p for p in data.get("target_paths", [])
                if bool(p) and Path(p).suffix.lower() in IMAGE_EXTS and Path(p).exists()]

    @staticmethod
    def _config_summary(config: dict) -> str:
        """转换参数摘要（配置分节说明用）。"""
        fmt = config.get("format")
        out = config.get("output_dir") or "原图所在目录"
        return f"🖼️ 输出 {fmt} · 质量 {config.get('quality')}\n  📁 输出目录 {out}"

    def run_interactive(self, payload: dict) -> None:
        """手动 / 定时任务：控制台显示配置与逐张进度，倒计时退出。"""
        images = self._collect_images(payload)
        if not images:
            print_banner(title())
            print()
            print("  ❌ 未选择有效的图片文件")
            countdown_exit()
            return

        config = self._resolve_params(payload)
        try:
            converter = ImageConverter(config)
        except (FileNotFoundError, ValueError) as e:
            print_banner(title())
            print(f"  ❌ {e}")
            countdown_exit()
            return

        print_banner(title())
        print()

        print_section("配置")
        print(f"  {self._config_summary(config)}")

        print_section("处理")
        success = failed = 0
        for image in images:
            ok, detail, output = converter.convert_one(image)
            name = Path(image).name
            if ok and output:
                size = ImageConverter.get_file_size(output)
                print(f"  ✅ {name} → {Path(output).name}（{size}）")
                success += 1
            else:
                first = next((ln.strip() for ln in (detail or "").splitlines() if ln.strip()),
                             detail or "未知错误")
                print(f"  ❌ {name}  {first}")
                failed += 1

        print_section("结果")
        parts = []
        if success:
            parts.append(f"✅ 成功 {success} 张")
        if failed:
            parts.append(f"❌ 失败 {failed} 张")
        print("  " + (" · ".join(parts) if parts else "  无结果"))
        print()
        countdown_exit()

    def run_node(self, payload: dict) -> None:
        """节点模式：被其他脚本联动调用时无头批量转换，结果写信封（不弹窗/不倒计时）。"""
        images = self._collect_images(payload)
        if not images:
            self._node_envelope(payload, 1, "未选择有效的图片文件", [])
            return

        config = self._resolve_params(payload)
        try:
            converter = ImageConverter(config)
        except (FileNotFoundError, ValueError) as e:
            self._node_envelope(payload, 1, str(e), [])
            return

        done, failed = [], []
        for img in images:
            ok, detail, out = converter.convert_one(img)
            if ok and out:
                done.append(out)
            else:
                failed.append(img)

        if done:
            msg = f"转换完成，成功 {len(done)} 张" + (f"，失败 {len(failed)} 张" if failed else "")
            self._node_envelope(payload, 0, msg, done)
        else:
            self._node_envelope(payload, 1, "全部转换失败", [])

    @staticmethod
    def _node_envelope(payload: dict, code: int, msg: str, output_paths: list) -> None:
        """信封固定 {code, msg, output_paths}，业务键顶层平铺。"""
        env = payload["environment"]
        with open(env["output_json"], "w", encoding="utf-8") as f:
            json.dump({"code": code, "msg": str(msg), "output_paths": output_paths},
                      f, ensure_ascii=False)


# ============ 入口 ============
def main():
    """主入口。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    param_path = sys.argv[1] if len(sys.argv) > 1 else None
    if not param_path:
        print_banner(title())
        print()
        print("  📌 使用说明")
        print("  ── 请通过不忙脚本盒子启动本脚本 ──")
        print()
        print("   ① 打开盒子，点击脚本卡片；或选中图片文件后")
        print("      右键 → 「图片格式转换」/ 按下全局快捷键")
        print("   ② 在弹出的参数窗口中选择输出格式、质量、输出目录")
        print("   ③ 点击「执行」即可一键转换")
        print()
        print("  🔔 参数窗口由脚本盒子渲染，脚本无需额外配置界面")
        print()
        pause_exit()

    payload = _read_payload(param_path)
    if payload is None:
        print("❌ 未获取到有效的参数文件")
        time.sleep(3)
        return

    env = payload.get("environment") or {}
    if env.get("invoke_mode") == "node":
        App().run_node(payload)          # 被联动调用 → 无头转换 + 写信封
    else:
        App().run_interactive(payload)   # 手动 / 定时任务 → 控制台展示


if __name__ == "__main__":
    main()