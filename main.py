"""
图片格式转换 - 支持多种图片格式互转
支持格式: PNG | JPEG | WEBP | BMP | GIF | ICO | TIFF
"""
import ctypes
import json
import os

import sys
import time

from pathlib import Path

from scr.gui import App
from scr.converter import ImageConverter



def get_path(param_path):
    initial_files = []

    if param_path and Path(param_path).exists():
        with open(param_path, "r", encoding="utf-8") as f:
            params = json.load(f)
        raw = params.get("data", {}).get("target_paths", [])
        initial_files = [p for p in raw if Path(p).exists()]
    return initial_files


def get_config():
    """读取配置文件，不存在则返回默认配置"""
    config_path = Path(__file__).parent / "config.json"

    # 默认配置
    default_config = {
        "format": "PNG",
        "output_dir": "",
        "quality": 85
    }

    if not os.path.exists(config_path):
        return default_config

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
            return {**default_config, **config}
    except (json.JSONDecodeError, ValueError) as e:
        print(f"配置文件格式错误：{e}，使用默认配置")
        return default_config


def cli(img_path: list, config: dict):
    print("-" * 50)
    print('图片格式转换')
    print("-" * 50)
    converter = ImageConverter(
        images=img_path,
        output_dir=config["output_dir"],
        quality=int(config["quality"]),
        output_format=config["format"],
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


def main():
    param_path = sys.argv[1] if len(sys.argv) > 1 else None
    config = get_config()
    if param_path:
        paths = get_path(param_path)
        cli(paths, config)
    else:
        if sys.platform == 'win32':
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                '瞎忙软件开发工作室.图片格式转换.图片格式转换.v0.0.1')
        app = App(config)
        app.mainloop()


if __name__ == "__main__":
    main()
