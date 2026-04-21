"""
LabelMe JSON 批量合并脚本
用途：将两个文件夹中同名的LabelMe标注JSON一一对应合并，输出到第三个文件夹
用法：python merge_labelme_batch.py --dir_a 文件夹A --dir_b 文件夹B --out 输出文件夹

可选参数：
  --suffix_a   标注A重名时加的后缀（默认：A）
  --suffix_b   标注B重名时加的后缀（默认：B）
  --skip_mismatch  遇到只在一个文件夹存在的文件时跳过（默认：直接复制过去）
"""

import json
import copy
import argparse
from pathlib import Path


# ── 基础 IO ──────────────────────────────────────────────────────────────────

def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data: dict, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── 单文件合并逻辑 ────────────────────────────────────────────────────────────

def get_labels(data: dict) -> set:
    return {s["label"] for s in data.get("shapes", [])}


def rename_shapes(shapes: list, suffix: str, conflicts: set) -> list:
    result = []
    for shape in shapes:
        s = copy.deepcopy(shape)
        if s["label"] in conflicts:
            s["label"] = f"{s['label']}_{suffix}"
        result.append(s)
    return result


def merge_two(data_a: dict, data_b: dict,
              suffix_a: str, suffix_b: str,
              name: str) -> tuple[dict, dict]:
    """
    合并两个LabelMe dict，返回 (merged_dict, stats_dict)
    """
    if data_a.get("imagePath") != data_b.get("imagePath"):
        print(f"  ⚠️  imagePath不一致，以A为准")

    conflicts = get_labels(data_a) & get_labels(data_b)
    if conflicts:
        shapes_a = rename_shapes(data_a.get("shapes", []), suffix_a, conflicts)
        shapes_b = rename_shapes(data_b.get("shapes", []), suffix_b, conflicts)
    else:
        shapes_a = data_a.get("shapes", [])
        shapes_b = data_b.get("shapes", [])

    merged = copy.deepcopy(data_a)
    merged["shapes"] = shapes_a + shapes_b

    stats = {
        "file": name,
        "shapes_a": len(data_a.get("shapes", [])),
        "shapes_b": len(data_b.get("shapes", [])),
        "shapes_merged": len(merged["shapes"]),
        "conflicts": sorted(conflicts) if conflicts else [],
    }
    return merged, stats


# ── 批量处理 ──────────────────────────────────────────────────────────────────

def batch_merge(dir_a: Path, dir_b: Path, dir_out: Path,
                suffix_a: str, suffix_b: str, skip_mismatch: bool):

    dir_out.mkdir(parents=True, exist_ok=True)

    files_a = {f.name for f in dir_a.glob("*.json")}
    files_b = {f.name for f in dir_b.glob("*.json")}

    common   = files_a & files_b
    only_a   = files_a - files_b
    only_b   = files_b - files_a

    print(f"\n📂 文件夹A: {dir_a}  ({len(files_a)} 个JSON)")
    print(f"📂 文件夹B: {dir_b}  ({len(files_b)} 个JSON)")
    print(f"📂 输出到 : {dir_out}")
    print(f"\n🔗 可匹配文件: {len(common)} 个")
    if only_a:
        print(f"⚠️  仅A有: {sorted(only_a)}")
    if only_b:
        print(f"⚠️  仅B有: {sorted(only_b)}")
    print("-" * 50)

    all_stats = []
    ok, skip, copy_count = 0, 0, 0

    # 1. 合并共有文件
    for name in sorted(common):
        print(f"🔀 合并: {name}")
        data_a = load_json(dir_a / name)
        data_b = load_json(dir_b / name)
        merged, stats = merge_two(data_a, data_b, suffix_a, suffix_b, name)
        save_json(merged, dir_out / name)
        if stats["conflicts"]:
            print(f"   重名label已重命名: {stats['conflicts']}")
        print(f"   A:{stats['shapes_a']} + B:{stats['shapes_b']} → 合并:{stats['shapes_merged']}")
        all_stats.append(stats)
        ok += 1

    # 2. 处理只在一个文件夹存在的文件
    for name in sorted(only_a | only_b):
        src_dir = dir_a if name in only_a else dir_b
        tag     = "A" if name in only_a else "B"
        if skip_mismatch:
            print(f"⏭️  跳过 (仅{tag}有): {name}")
            skip += 1
        else:
            print(f"📋 直接复制 (仅{tag}有): {name}")
            save_json(load_json(src_dir / name), dir_out / name)
            copy_count += 1

    # 3. 汇总
    print("\n" + "=" * 50)
    print(f"✅ 完成！合并: {ok} 个 | 复制: {copy_count} 个 | 跳过: {skip} 个")
    total_shapes = sum(s["shapes_merged"] for s in all_stats)
    print(f"📊 合并文件共含标注区域: {total_shapes} 个")

    # 输出有冲突的文件列表
    conflict_files = [s for s in all_stats if s["conflicts"]]
    if conflict_files:
        print(f"\n🔁 发生label重命名的文件 ({len(conflict_files)} 个):")
        for s in conflict_files:
            print(f"   {s['file']}: {s['conflicts']}")


# ── 入口 ──────────────────────────────────────────────────────────────────────
# python merge_labelme_batch.py \
#   --dir_a 标注者甲/ \
#   --dir_b 标注者乙/ \
#   --out   合并结果/
def main():
    parser = argparse.ArgumentParser(description="批量合并两个文件夹下的LabelMe JSON标注")
    parser.add_argument("--dir_a",  required=True, help="标注文件夹A的路径")
    parser.add_argument("--dir_b",  required=True, help="标注文件夹B的路径")
    parser.add_argument("--out",    required=True, help="输出文件夹路径")
    parser.add_argument("--suffix_a", default="A", help="A的重名后缀（默认：A）")
    parser.add_argument("--suffix_b", default="B", help="B的重名后缀（默认：B）")
    parser.add_argument("--skip_mismatch", action="store_true",
                        help="只在一个文件夹存在的文件直接跳过（默认：直接复制）")
    args = parser.parse_args()

    batch_merge(
        Path(args.dir_a), Path(args.dir_b), Path(args.out),
        args.suffix_a, args.suffix_b, args.skip_mismatch
    )


if __name__ == "__main__":
    main()