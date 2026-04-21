"""
检查图像和mask是RGB还是灰度图
用法：python check_mode.py --img_dir data/imgs/ --mask_dir data/masks/
"""

from pathlib import Path
from PIL import Image
from collections import Counter
import argparse


def check_folder(folder: Path, exts=(".png", ".jpg", ".jpeg", ".bmp", ".tif")):
    files = [f for f in sorted(folder.iterdir()) if f.suffix.lower() in exts]
    if not files:
        print(f"  ❌ 未找到图像文件")
        return

    mode_counter = Counter()
    details = []

    for f in files:
        img = Image.open(f)
        mode_counter[img.mode] += 1
        details.append((f.name, img.mode, img.size))

    # 汇总
    print(f"  📊 共 {len(files)} 张，模式分布：")
    for mode, count in mode_counter.most_common():
        desc = {
            "RGB":  "彩色三通道 ✅",
            "L":    "灰度图 ✅",
            "RGBA": "彩色+透明通道 ⚠️  （含Alpha，可能需转RGB）",
            "P":    "调色板模式 ⚠️  （可能需转L或RGB）",
            "I":    "32位整数灰度 ⚠️",
            "F":    "32位浮点灰度 ⚠️",
            "1":    "二值图（黑白）⚠️",
        }.get(mode, f"其他模式")
        print(f"    [{mode}] {count} 张 — {desc}")

    # 如果存在多种模式，列出异常文件
    if len(mode_counter) > 1:
        majority_mode = mode_counter.most_common(1)[0][0]
        print(f"\n  ⚠️  存在多种模式！主流模式为 [{majority_mode}]，以下文件不一致：")
        for name, mode, size in details:
            if mode != majority_mode:
                print(f"    {name}  →  [{mode}]  尺寸:{size}")
    else:
        print(f"  ✅ 所有文件模式一致：[{list(mode_counter.keys())[0]}]")


def main():
    parser = argparse.ArgumentParser(description="检查图像和mask的颜色模式")
    parser.add_argument("--img_dir",  default=r'D:\yan\datas\f13_zuobiaots1024\20200514141725', help="原始图像文件夹路径")
    parser.add_argument("--mask_dir", default=r'D:\yan\datas\f13_zuobiaots1024\20200514141725', help="mask文件夹路径")
    args = parser.parse_args()

    if args.img_dir:
        print(f"\n🖼️  图像文件夹: {args.img_dir}")
        check_folder(Path(args.img_dir))

    if args.mask_dir:
        print(f"\n🎭  Mask文件夹: {args.mask_dir}")
        check_folder(Path(args.mask_dir))

    if not args.img_dir and not args.mask_dir:
        print("请至少指定 --img_dir 或 --mask_dir 其中一个")


if __name__ == "__main__":
    main()