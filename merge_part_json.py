"""
合并两套 labelme 标注 JSON 文件
- 标注集A：提取 lipid-rich → 重命名为 lipid
- 标注集B：提取 lumen → 保持 lumen
- 同名图像的标注合并为一个 JSON；某一方无目标类别则只保留另一方

目录结构要求（两个目录中的 JSON 文件名需与图像名对应，互相匹配）：
    dir_a/   0001.json, 0002.json, ...
    dir_b/   0001.json, 0002.json, ...

用法：
    python merge_labelme_annotations.py --dir_a  <标注集A目录> --dir_b  <标注集B目录> --output <输出目录>

可选参数：
    --label_a   标注集A中要提取的类别名，默认 lipid-rich
    --rename_a  提取后重命名为，默认 lipid
    --label_b   标注集B中要提取的类别名，默认 lumen
    --rename_b  提取后重命名为，默认 lumen（不改）
"""

import argparse
import copy
import json
import sys
from pathlib import Path


# ──────────────────────────────────────────────
# 核心逻辑
# ──────────────────────────────────────────────

def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def extract_shapes(labelme_data: dict, target_label: str, rename_to: str) -> list:
    """
    从 labelme JSON 中提取指定类别的 shapes，并重命名。
    返回筛选 + 重命名后的 shapes 列表（可能为空）。
    """
    result = []
    for shape in labelme_data.get("shapes", []):
        if shape.get("label", "").strip() == target_label:
            s = copy.deepcopy(shape)
            s["label"] = rename_to
            result.append(s)
    return result


def merge_pair(data_a: dict | None, shapes_a: list,
               data_b: dict | None, shapes_b: list) -> dict | None:
    """
    将两组 shapes 合并到一个 labelme JSON。
    以有数据的一方作为模板（优先 A），imageData 字段置为 None 以节省体积。
    若两方都没有目标标注，返回 None。
    """
    merged_shapes = shapes_a + shapes_b
    if not merged_shapes:
        return None

    # 选模板：优先 A，否则用 B
    template = copy.deepcopy(data_a if data_a is not None else data_b)

    # 移除嵌入的 base64 图像数据（通常很大，mask 生成不需要）
    # 如果您需要保留，可注释掉下面这行
    template["imageData"] = None

    template["shapes"] = merged_shapes
    return template


# ──────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="合并两套 labelme 标注")
    parser.add_argument("--dir_a",    required=True, help="标注集A目录")
    parser.add_argument("--dir_b",    required=True, help="标注集B目录")
    parser.add_argument("--output",   required=True, help="输出目录")
    parser.add_argument("--label_a",  default="lipid-rich", help="A中目标类别名（默认 lipid-rich）")
    parser.add_argument("--rename_a", default="lipid",      help="A提取后重命名（默认 lipid）")
    parser.add_argument("--label_b",  default="1",      help="B中目标类别名（默认 lumen）")
    parser.add_argument("--rename_b", default="lumen",      help="B提取后重命名（默认 lumen）")
    args = parser.parse_args()

    dir_a  = Path(args.dir_a)
    dir_b  = Path(args.dir_b)
    outdir = Path(args.output)

    if not dir_a.exists():
        print(f"[错误] 标注集A目录不存在: {dir_a}"); sys.exit(1)
    if not dir_b.exists():
        print(f"[错误] 标注集B目录不存在: {dir_b}"); sys.exit(1)

    # 收集所有 JSON 文件名（stem → path）
    files_a = {f.stem: f for f in dir_a.glob("*.json")}
    files_b = {f.stem: f for f in dir_b.glob("*.json")}

    all_stems = sorted(set(files_a) | set(files_b))
    if not all_stems:
        print("[警告] 两个目录中均未找到 JSON 文件"); sys.exit(0)

    print(f"A 目录 JSON 数: {len(files_a)}")
    print(f"B 目录 JSON 数: {len(files_b)}")
    print(f"合集图像数:     {len(all_stems)}")
    print(f"提取规则: A['{args.label_a}'] → '{args.rename_a}'  |  "
          f"B['{args.label_b}'] → '{args.rename_b}'")
    print(f"输出目录: {outdir}\n")

    stats = {
        "both":      0,  # A+B 都有目标标注
        "only_a":    0,  # 只有 A 有
        "only_b":    0,  # 只有 B 有
        "neither":   0,  # 两方都没有 → 跳过
        "a_missing": 0,  # A 目录中根本没有该图的 JSON
        "b_missing": 0,  # B 目录中根本没有该图的 JSON
    }

    for stem in all_stems:
        path_a = files_a.get(stem)
        path_b = files_b.get(stem)

        # 读取并提取
        data_a, shapes_a = None, []
        if path_a:
            data_a = load_json(path_a)
            shapes_a = extract_shapes(data_a, args.label_a, args.rename_a)
        else:
            stats["a_missing"] += 1

        data_b, shapes_b = None, []
        if path_b:
            data_b = load_json(path_b)
            shapes_b = extract_shapes(data_b, args.label_b, args.rename_b)
        else:
            stats["b_missing"] += 1

        # 统计
        has_a = len(shapes_a) > 0
        has_b = len(shapes_b) > 0
        if has_a and has_b:
            stats["both"] += 1
        elif has_a:
            stats["only_a"] += 1
        elif has_b:
            stats["only_b"] += 1
        else:
            stats["neither"] += 1

        # 合并
        merged = merge_pair(data_a, shapes_a, data_b, shapes_b)
        if merged is None:
            # 两方都无目标标注，跳过
            continue

        # 写出
        out_path = outdir / f"{stem}.json"
        save_json(merged, out_path)

    # ── 汇总报告 ──
    total_written = stats["both"] + stats["only_a"] + stats["only_b"]
    print("=" * 48)
    print(f"  输出 JSON 总数:            {total_written}")
    print(f"  A+B 均有目标标注:          {stats['both']}")
    print(f"  仅 A 有目标标注 (lipid):   {stats['only_a']}")
    print(f"  仅 B 有目标标注 (lumen):   {stats['only_b']}")
    print(f"  两方均无目标标注 (跳过):   {stats['neither']}")
    print(f"  A 目录缺少对应 JSON:       {stats['a_missing']}")
    print(f"  B 目录缺少对应 JSON:       {stats['b_missing']}")
    print("=" * 48)
    print("完成！")


if __name__ == "__main__":
    main()