import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List
from scr.gui import ALL_WRITE_FORMATS



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
