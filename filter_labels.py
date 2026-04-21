"""
从合并后的 labelme JSON 目录中，筛选同时含有 lipid 和 lumen 标注的文件，
复制到新目录；并将对应图像从图像目录复制到另一新目录。

用法：
    python filter_labels.py --json_dir ../data/gq_zz/jsons --image_dir ../data/gq_zz/JPEGImages_L --out_json ../data/gq_zz/part_jsons --out_image ../data/gq_zz/part_JPEGImages_L

可选参数：
    --label_a   第一个类别名，默认 lipid
    --label_b   第二个类别名，默认 lumen
    --exts      图像扩展名，默认 .jpg .jpeg .png .bmp .tif .tiff
"""

import argparse
import json
import shutil
import sys
from pathlib import Path


def has_both_labels(json_path: Path, label_a: str, label_b: str) -> bool:
    """检查 JSON 文件中是否同时含有 label_a 和 label_b。"""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    labels = {s.get("label", "").strip() for s in data.get("shapes", [])}
    return label_a in labels and label_b in labels


def find_image(image_dir: Path, stem: str, exts: list[str]) -> Path | None:
    """在 image_dir 中按文件名 stem 查找图像，返回第一个匹配路径。"""
    for ext in exts:
        candidate = image_dir / (stem + ext)
        if candidate.exists():
            return candidate
    return None


def main():
    parser = argparse.ArgumentParser(description="筛选同时含 lipid+lumen 的 JSON 并复制对应图像")
    parser.add_argument("--json_dir",  required=True, help="合并后 JSON 目录")
    parser.add_argument("--image_dir", required=True, help="原始图像目录")
    parser.add_argument("--out_json",  required=True, help="输出 JSON 目录")
    parser.add_argument("--out_image", required=True, help="输出图像目录")
    parser.add_argument("--label_a",   default="lipid", help="类别A名称（默认 lipid）")
    parser.add_argument("--label_b",   default="lumen", help="类别B名称（默认 lumen）")
    parser.add_argument(
        "--exts",
        nargs="+",
        default=[".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"],
        help="图像扩展名（默认 .jpg .jpeg .png .bmp .tif .tiff）",
    )
    args = parser.parse_args()

    json_dir  = Path(args.json_dir)
    image_dir = Path(args.image_dir)
    out_json  = Path(args.out_json)
    out_image = Path(args.out_image)

    if not json_dir.exists():
        print(f"[错误] JSON 目录不存在: {json_dir}"); sys.exit(1)
    if not image_dir.exists():
        print(f"[错误] 图像目录不存在: {image_dir}"); sys.exit(1)

    out_json.mkdir(parents=True, exist_ok=True)
    out_image.mkdir(parents=True, exist_ok=True)

    # 归一化扩展名（小写，带点）
    exts = [e if e.startswith(".") else f".{e}" for e in args.exts]
    exts_lower = [e.lower() for e in exts]

    all_jsons = sorted(json_dir.glob("*.json"))
    if not all_jsons:
        print(f"[警告] JSON 目录中未找到任何 .json 文件: {json_dir}"); sys.exit(0)

    print(f"JSON 总数:    {len(all_jsons)}")
    print(f"筛选条件:     同时含 '{args.label_a}' 和 '{args.label_b}'")
    print(f"JSON 输出:    {out_json}")
    print(f"图像输出:     {out_image}\n")

    stats = {
        "matched":       0,   # 同时含两个类别
        "json_copied":   0,
        "image_copied":  0,
        "image_missing": 0,   # JSON 匹配但找不到图像
        "json_error":    0,   # 读取 JSON 失败
    }
    missing_images = []

    for jp in all_jsons:
        # 读取并判断
        try:
            matched = has_both_labels(jp, args.label_a, args.label_b)
        except Exception as e:
            print(f"  [读取失败] {jp.name}: {e}")
            stats["json_error"] += 1
            continue

        if not matched:
            continue

        stats["matched"] += 1

        # 复制 JSON
        shutil.copy2(jp, out_json / jp.name)
        stats["json_copied"] += 1

        # 查找并复制图像
        img_path = find_image(image_dir, jp.stem, exts_lower)
        if img_path:
            shutil.copy2(img_path, out_image / img_path.name)
            stats["image_copied"] += 1
        else:
            stats["image_missing"] += 1
            missing_images.append(jp.stem)

    # ── 汇总报告 ──
    print("=" * 50)
    print(f"  扫描 JSON 总数:             {len(all_jsons)}")
    print(f"  同时含两类别 (匹配):        {stats['matched']}")
    print(f"  JSON 已复制:                {stats['json_copied']}")
    print(f"  图像已复制:                 {stats['image_copied']}")
    print(f"  图像未找到 (仅复制JSON):    {stats['image_missing']}")
    if stats["json_error"]:
        print(f"  JSON 读取失败:              {stats['json_error']}")
    print("=" * 50)

    if missing_images:
        print("\n[警告] 以下文件的图像未在图像目录中找到：")
        for name in missing_images:
            print(f"  {name}")

    print("\n完成！")


if __name__ == "__main__":
    main()