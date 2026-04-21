"""
LabelMe JSON → 多类别 Mask PNG 批量生成脚本（含彩色可视化版）
用途：将合并后的LabelMe JSON文件夹批量转换为：
      1. 训练用数值mask（masks/）         像素值 = class_id (0,1,2,3...)
      2. 肉眼可视化彩色mask（masks_color/） 每个类别对应不同颜色

用法：python json2mask.py --json_dir ../data/2600_bankuai/Annotations/ --out_dir ../data/2600_bankuai/bk_masks/

依赖安装：
    pip install numpy pillow
"""

"""
LabelMe JSON → 多类别 Mask PNG 批量生成脚本（含彩色可视化版）- 修复版
修复：
  1. 绘制顺序按面积从大到小排序，小目标不再被大区域覆盖
  2. 增加不支持shape_type的收集与汇总报告
  3. 增加坐标越界检测
  4. polygon自交检测提示
"""

import json
import argparse
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw

PALETTE = [
    (0,   0,   0  ),
    (220, 50,  50 ),
    (50,  180, 50 ),
    (50,  100, 220),
    (220, 180, 50 ),
    (180, 50,  220),
    (50,  200, 200),
    (220, 120, 50 ),
    (120, 220, 180),
    (220, 50,  150),
    (100, 150, 220),
    (180, 220, 50 ),
]

def get_color(class_id: int) -> tuple:
    if class_id < len(PALETTE):
        return PALETTE[class_id]
    np.random.seed(class_id * 17)
    return tuple(np.random.randint(80, 230, 3).tolist())


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(data: dict, path: Path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def collect_all_labels(json_dir: Path) -> dict:
    labels = set()
    for p in sorted(json_dir.glob("*.json")):
        data = load_json(p)
        for shape in data.get("shapes", []):
            labels.add(shape["label"])
    return {label: idx + 1 for idx, label in enumerate(sorted(labels))}


def estimate_shape_area(shape: dict) -> float:
    """估算shape面积，用于排序（大面积先画，小面积后画）"""
    shape_type = shape.get("shape_type", "polygon")
    points = shape["points"]

    if shape_type == "polygon" and len(points) >= 3:
        # Shoelace公式估算多边形面积
        pts = np.array(points)
        x, y = pts[:, 0], pts[:, 1]
        area = 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))
        return area
    elif shape_type == "rectangle" and len(points) >= 2:
        x1, y1 = points[0]
        x2, y2 = points[1]
        return abs(x2 - x1) * abs(y2 - y1)
    elif shape_type == "circle" and len(points) >= 2:
        cx, cy = points[0]
        px, py = points[1]
        r = ((cx - px) ** 2 + (cy - py) ** 2) ** 0.5
        return np.pi * r * r
    else:
        return 0.0


def shapes_to_mask(shapes: list, height: int, width: int,
                   label_map: dict, filename: str = "") -> tuple[np.ndarray, list]:
    """
    返回: (mask数组, 跳过shape列表)
    核心修复: 按面积降序排列shapes，确保小目标绘制在大区域之上
    """
    mask = Image.fromarray(np.zeros((height, width), dtype=np.uint8))
    draw = ImageDraw.Draw(mask)
    skipped = []

    # ★ 关键修复：按面积从大到小排序，小的后画（不被覆盖）
    sorted_shapes = sorted(shapes, key=estimate_shape_area, reverse=True)

    for shape in sorted_shapes:
        label      = shape["label"]
        shape_type = shape.get("shape_type", "polygon")
        class_id   = label_map.get(label, 0)
        points     = shape["points"]

        # 坐标越界检测
        for px, py in points:
            if not (0 <= px <= width and 0 <= py <= height):
                print(f"  ⚠️  [{filename}] label='{label}' 存在越界坐标 ({px:.1f}, {py:.1f})，"
                      f"图像尺寸={width}x{height}，已裁剪至边界")
                break

        # 坐标裁剪到图像范围内
        clipped = [[min(max(p[0], 0), width - 1),
                    min(max(p[1], 0), height - 1)] for p in points]

        if shape_type == "polygon":
            if len(clipped) < 3:
                skipped.append((label, shape_type, "点数不足3"))
                continue
            draw.polygon([tuple(p) for p in clipped], fill=class_id)

        elif shape_type == "rectangle":
            if len(clipped) < 2:
                skipped.append((label, shape_type, "点数不足2"))
                continue
            x1, y1 = clipped[0]
            x2, y2 = clipped[1]
            # 确保x1<x2, y1<y2（LabelMe rectangle有时会反向）
            draw.rectangle([min(x1,x2), min(y1,y2), max(x1,x2), max(y1,y2)],
                           fill=class_id)

        elif shape_type == "circle":
            if len(clipped) < 2:
                skipped.append((label, shape_type, "点数不足2"))
                continue
            cx, cy = points[0]
            px, py = points[1]
            r = ((cx - px) ** 2 + (cy - py) ** 2) ** 0.5
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=class_id)

        else:
            skipped.append((label, shape_type, "不支持的类型"))

    return np.array(mask, dtype=np.uint8), skipped


def mask_to_color(mask_arr: np.ndarray, label_map: dict) -> Image.Image:
    h, w = mask_arr.shape
    color_img = np.zeros((h, w, 3), dtype=np.uint8)

    id_to_label = {v: k for k, v in label_map.items()}
    id_to_label[0] = "background"

    present_ids = np.unique(mask_arr).tolist()
    for cid in present_ids:
        color_img[mask_arr == cid] = get_color(cid)

    pil_img = Image.fromarray(color_img, mode="RGB")

    box_size  = max(12, h // 40)
    padding   = box_size // 2
    line_gap  = box_size + padding
    legend_ids = [cid for cid in present_ids if cid != 0]

    if not legend_ids:
        return pil_img

    legend_h = line_gap * len(legend_ids) + padding * 2
    legend_w = max(140, w // 4)
    lx = w - legend_w - padding
    ly = h - legend_h - padding

    overlay = Image.new("RGBA", pil_img.size, (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)
    ov_draw.rectangle(
        [lx - padding, ly - padding, w - padding, h - padding],
        fill=(0, 0, 0, 160)
    )
    pil_img = Image.alpha_composite(pil_img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(pil_img)

    for i, cid in enumerate(legend_ids):
        color = get_color(cid)
        bx = lx
        by = ly + i * line_gap
        draw.rectangle([bx, by, bx + box_size, by + box_size], fill=color)
        label_text = id_to_label.get(cid, str(cid))
        draw.text((bx + box_size + padding, by), f"{cid}: {label_text}",
                  fill=(255, 255, 255))

    return pil_img


def batch_json2mask(json_dir: Path, out_dir: Path):
    out_mask_dir  = out_dir
    out_color_dir = out_dir.parent / (out_dir.name + "_color")
    out_mask_dir.mkdir(parents=True, exist_ok=True)
    out_color_dir.mkdir(parents=True, exist_ok=True)

    json_files = sorted(json_dir.glob("*.json"))
    if not json_files:
        print(f"❌ 在 {json_dir} 下未找到任何JSON文件")
        return

    print(f"📂 扫描JSON文件夹: {json_dir}  ({len(json_files)} 个文件)")
    print("🏷️  收集所有label...")
    label_map = collect_all_labels(json_dir)

    print(f"   共 {len(label_map)} 个label类别：")
    for label, cid in label_map.items():
        print(f"   [{cid:>3}] {label:20s}  颜色RGB{get_color(cid)}")

    label_map_path = out_mask_dir / "label_map.json"
    save_json({"background": 0, **label_map}, label_map_path)
    print(f"\n💾 label映射已保存: {label_map_path}")
    print("-" * 60)

    ok, skip_file = 0, 0
    all_skipped_shapes = []  # 汇总所有被跳过的shape信息

    for p in json_files:
        data   = load_json(p)
        height = data.get("imageHeight")
        width  = data.get("imageWidth")

        if not height or not width:
            print(f"⚠️  跳过 {p.name}：缺少 imageHeight/imageWidth")
            skip_file += 1
            continue

        shapes   = data.get("shapes", [])
        mask_arr, skipped = shapes_to_mask(shapes, height, width, label_map, p.name)

        if skipped:
            for label, stype, reason in skipped:
                all_skipped_shapes.append((p.name, label, stype, reason))

        Image.fromarray(mask_arr).save(out_mask_dir / (p.stem + ".png"))
        mask_to_color(mask_arr, label_map).save(out_color_dir / (p.stem + ".png"))

        unique_ids  = np.unique(mask_arr).tolist()
        id_to_label = {v: k for k, v in label_map.items()}
        id_to_label[0] = "background"
        labels_present = [f"{i}:{id_to_label.get(i,'?')}" for i in unique_ids]

        # ★ 缺失类别检测：检查JSON里有哪些label但mask里没出现
        expected_ids = set(label_map[s["label"]] for s in shapes
                           if s["label"] in label_map)
        missing_ids  = expected_ids - set(unique_ids)
        if missing_ids:
            missing_labels = [f"{i}:{id_to_label.get(i,'?')}" for i in missing_ids]
            print(f"⚠️  {p.name:30s}  ❗缺失: {missing_labels}  含: {labels_present}")
        else:
            print(f"✅ {p.name:30s}  含: {labels_present}")
        ok += 1

    print("-" * 60)

    # 汇总跳过的shape
    if all_skipped_shapes:
        print(f"\n⚠️  共有 {len(all_skipped_shapes)} 个shape被跳过：")
        for fname, label, stype, reason in all_skipped_shapes:
            print(f"   {fname} | label={label} | type={stype} | 原因={reason}")

    print(f"\n🎉 完成！处理: {ok} 张 | 跳过: {skip_file} 个文件")
    print(f"📁 训练用数值mask : {out_mask_dir.resolve()}")
    print(f"🎨 彩色可视化mask : {out_color_dir.resolve()}")
    print(f"📋 label映射表    : {label_map_path.resolve()}")


def main():
    parser = argparse.ArgumentParser(
        description="LabelMe JSON批量转多类别Mask PNG（含彩色可视化）- 修复版"
    )
    parser.add_argument("--json_dir", required=True, help="合并后的JSON文件夹路径")
    parser.add_argument("--out_dir",  required=True, help="数值mask输出文件夹路径")
    args = parser.parse_args()
    batch_json2mask(Path(args.json_dir), Path(args.out_dir))


if __name__ == "__main__":
    main()