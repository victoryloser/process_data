import os
import json
import shutil


def extract_stent_jsons_and_images(src_dir, dst_dir, target_class="stent"):
    """
    筛选包含特定类别的 labelme json 文件，并连同其原图一起复制到指定文件夹
    """
    if not os.path.exists(dst_dir):
        os.makedirs(dst_dir)
        print(f"已创建目标文件夹: {dst_dir}")

    count = 0

    for filename in os.listdir(src_dir):
        if filename.endswith(".json"):
            json_path = os.path.join(src_dir, filename)

            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                if "shapes" in data:
                    has_target = False
                    for shape in data["shapes"]:
                        if shape.get("label") == target_class:
                            has_target = True
                            break

                    if has_target:
                        # 1. 复制 JSON 文件
                        dst_json_path = os.path.join(dst_dir, filename)
                        shutil.copy2(json_path, dst_json_path)

                        # 2. 寻找并复制对应的图片文件
                        img_copied = False
                        img_name_from_json = data.get("imagePath")
                        base_name = os.path.splitext(filename)[0]

                        # 构建候选图片名称列表（优先使用 json 中记录的名称，其次尝试常见后缀）
                        candidate_images = []
                        if img_name_from_json:
                            # 提取文件名，防止 imagePath 带有绝对路径
                            candidate_images.append(os.path.basename(img_name_from_json))
                        candidate_images.extend([f"{base_name}.jpg", f"{base_name}.png", f"{base_name}.jpeg"])

                        for img_name in candidate_images:
                            src_img_path = os.path.join(src_dir, img_name)
                            if os.path.exists(src_img_path):
                                dst_img_path = os.path.join(dst_dir, img_name)
                                shutil.copy2(src_img_path, dst_img_path)
                                img_copied = True
                                break  # 找到并成功复制图片后，跳出寻找图片的循环

                        if img_copied:
                            print(f"已复制: {filename} 及其原图")
                        else:
                            print(f"已复制: {filename} (⚠️ 未能在源文件夹中找到对应的图片)")

                        count += 1

            except json.JSONDecodeError:
                print(f"警告: {filename} 不是有效的 JSON 文件，已跳过。")
            except Exception as e:
                print(f"处理 {filename} 时发生错误: {e}")

    print("-" * 30)
    print(f"处理完成！共找到了 {count} 组包含 '{target_class}' 类的文件。")


if __name__ == "__main__":
    # ==========================================
    # 请在这里修改为你的实际文件夹路径
    # ==========================================
    SOURCE_FOLDER = "../before"  # 存放原始 json 和图片的文件夹
    TARGET_FOLDER = "../before_stent"  # 筛选后存放 json 和图片的目标文件夹

    extract_stent_jsons_and_images(SOURCE_FOLDER, TARGET_FOLDER, target_class="stent")