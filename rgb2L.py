"""
批量将RGB冠状动脉图像转换为灰度图
用法:
    python convert_to_grayscale.py --input_dir <输入目录> --output_dir <输出目录>

可选参数:
    --input_dir     包含所有图像的目录（RGB和灰度混合）
    --output_dir    输出目录（转换后的图像保存在此）
    --inplace       直接覆盖原文件（不需要 output_dir）
    --exts          要处理的扩展名，默认: .jpg .jpeg .png .bmp .tif .tiff
"""

import argparse
import os
import sys
from pathlib import Path
from PIL import Image


def is_rgb(img: Image.Image) -> bool:
    """判断图像是否为RGB（非灰度）格式"""
    return img.mode in ("RGB", "RGBA", "P", "CMYK", "YCbCr", "LAB", "HSV")


def convert_image(src_path: Path, dst_path: Path) -> str:
    """
    转换单张图像为灰度图。
    返回: 'converted' | 'skipped' | 'error:<msg>'
    """
    try:
        img = Image.open(src_path)
        if not is_rgb(img):
            # 已经是灰度图，直接复制（如果目标路径不同）
            if src_path != dst_path:
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                img.save(dst_path)
            return "skipped"

        # 转换为灰度
        gray = img.convert("L")
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        gray.save(dst_path)
        return "converted"
    except Exception as e:
        return f"error:{e}"


def main():
    parser = argparse.ArgumentParser(description="批量RGB→灰度图转换工具")
    parser.add_argument("--input_dir", required=True, help="输入图像目录")
    parser.add_argument("--output_dir", default=None, help="输出目录（与input_dir不同时保存）")
    parser.add_argument("--inplace", action="store_true", help="直接覆盖原文件")
    parser.add_argument(
        "--exts",
        nargs="+",
        default=[".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"],
        help="要处理的文件扩展名",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        print(f"[错误] 输入目录不存在: {input_dir}")
        sys.exit(1)

    if args.inplace:
        output_dir = input_dir
    elif args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        print("[错误] 请指定 --output_dir 或使用 --inplace 覆盖原文件")
        sys.exit(1)

    exts = {e.lower() for e in args.exts}

    # 收集所有图像文件
    files = [
        f for f in input_dir.rglob("*")
        if f.is_file() and f.suffix.lower() in exts
    ]

    if not files:
        print(f"[警告] 在 {input_dir} 中未找到图像文件")
        sys.exit(0)

    print(f"共找到 {len(files)} 张图像，开始处理...\n")

    stats = {"converted": 0, "skipped": 0, "error": 0}

    for i, src in enumerate(files, 1):
        # 保持目录结构
        rel = src.relative_to(input_dir)
        dst = output_dir / rel

        status = convert_image(src, dst)

        if status == "converted":
            stats["converted"] += 1
            label = "✓ 已转换"
        elif status == "skipped":
            stats["skipped"] += 1
            label = "- 已是灰度"
        else:
            stats["error"] += 1
            label = f"✗ 失败: {status[6:]}"

        # 每50张打印一次进度
        if i % 50 == 0 or i == len(files):
            print(f"[{i:>4}/{len(files)}] {label}: {src.name}")

    print(f"""
========================================
处理完成！
  转换 (RGB→灰度): {stats['converted']} 张
  跳过 (已是灰度): {stats['skipped']} 张
  失败:            {stats['error']} 张
输出目录: {output_dir}
========================================
""")

# python convert_to_grayscale.py --input_dir ./原始图像目录 --output_dir ./输出目录  新文件夹
# python convert_to_grayscale.py --input_dir ./原始图像目录 --inplace  覆盖
if __name__ == "__main__":
    main()