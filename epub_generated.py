#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
from pathlib import Path
from PIL import Image, ExifTags
import subprocess
import shutil

# ===== 基本路徑 =====
BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
MANUSCRIPT_DIR = BASE_DIR / "manuscript"
OUTPUT_DIR = BASE_DIR / "output"

OUTPUT_DIR.mkdir(exist_ok=True)

# ===== 合法檔名處理 =====
def clean_filename(name: str) -> str:
    name = re.sub(r"[^\w\-.]", "", name)
    return name

# ===== EXIF 旋轉處理 =====
def fix_exif_rotation(image_path: Path):
    try:
        img = Image.open(image_path)

        exif = img._getexif()
        if not exif:
            return

        orientation_key = None
        for key, value in ExifTags.TAGS.items():
            if value == "Orientation":
                orientation_key = key
                break

        if orientation_key and orientation_key in exif:
            orientation = exif[orientation_key]
            rotate_map = {
                3: 180,
                6: 270,
                8: 90
            }
            if orientation in rotate_map:
                img = img.rotate(rotate_map[orientation], expand=True)
                img.save(image_path)
                print(f"Fixed EXIF rotation: {image_path}")
    except Exception as e:
        print(f"Failed to fix EXIF for {image_path}: {e}")


# ====== 整理 assets 內所有圖片 ======
rename_map = {}

for img_path in ASSETS_DIR.glob("*"):
    if img_path.is_file():
        clean_name = clean_filename(img_path.name)

        # 自訂：如果想重新命名為純時間戳，可在這裡改
        clean_path = img_path.with_name(clean_name)

        if img_path.name != clean_name:
            img_path.rename(clean_path)
            print(f"Rename: {img_path.name} → {clean_name}")

        # 處理 EXIF 旋轉
        fix_exif_rotation(clean_path)

        # 建立 map（原始 → 新檔名）
        rename_map[img_path.name] = clean_name
        rename_map[clean_name] = clean_name


# ====== 更新 Markdown 內所有圖片連結 ======
md_files = list(MANUSCRIPT_DIR.glob("*.md"))

# 支援所有 Markdown 圖片語法
markdown_img_pattern = re.compile(r'!\[(.*?)\]\((.*?)\)')

for md_file in md_files:
    text = md_file.read_text(encoding="utf-8")

    def replace_link(match):
        alt_text = match.group(1)
        link = match.group(2)

        filename = Path(link).name  # 取出純檔名

        if filename in rename_map:
            new_name = rename_map[filename]
            # 永遠只保留檔名，避免 Pandoc 找不到
            return f"![]({new_name})"

        return match.group(0)

    new_text = markdown_img_pattern.sub(replace_link, text)

    md_file.write_text(new_text, encoding="utf-8")
    print(f"Updated Markdown: {md_file}")


# ====== EPUB 生成 ======
output_epub = OUTPUT_DIR / "book.epub"

cmd = [
    "pandoc",
    "-o", str(output_epub),
    "--toc",
    "--toc-depth=3",
    "--resource-path=assets",
]

# 加入所有 manuscript/*.md
for md_file in sorted(MANUSCRIPT_DIR.glob("*.md")):
    cmd.append(str(md_file))

print("\nRunning Pandoc...\n")
result = subprocess.run(cmd, capture_output=True, text=True)

if result.returncode == 0:
    print(f"EPUB 已完成：{output_epub}")
else:
    print("EPUB 生成失敗！")
    print(result.stderr)

