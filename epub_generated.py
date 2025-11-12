import os
import re
from pathlib import Path
from PIL import Image, ExifTags
import subprocess
import sys
import yaml

# ---------- 設定 ----------
MANUSCRIPT_DIR = Path("manuscript")
ASSETS_DIR = Path("assets")
OUTPUT_FILE = Path("output/output.epub")
METADATA_FILE = Path("metadata.yaml")

# ---------- 工具函數 ----------
def safe_filename(name: str) -> str:
    """將檔名轉成安全字元，保留英文、數字、中文、點號、連字號"""
    return re.sub(r'[^\w\.\-一-龥]', '', name)

def fix_image_orientation(img_path: Path):
    """修正圖片方向"""
    try:
        img = Image.open(img_path)
        for orientation in ExifTags.TAGS.keys():
            if ExifTags.TAGS[orientation]=='Orientation':
                break
        exif=dict(img._getexif().items()) if img._getexif() else {}
        val = exif.get(orientation, 1)
        if val == 3:
            img = img.rotate(180, expand=True)
        elif val == 6:
            img = img.rotate(270, expand=True)
        elif val == 8:
            img = img.rotate(90, expand=True)
        img.save(img_path)
    except Exception:
        pass

# ---------- 處理圖片 ----------
if not ASSETS_DIR.exists():
    print(f"[ERROR] Assets 資料夾不存在: {ASSETS_DIR}")
    sys.exit(1)

rename_map = {}
for img_path in ASSETS_DIR.iterdir():
    if img_path.suffix.lower() not in [".jpg", ".jpeg", ".png"]:
        continue
    new_name = safe_filename(img_path.stem) + img_path.suffix
    new_path = ASSETS_DIR / new_name
    if img_path != new_path:
        img_path.rename(new_path)
    fix_image_orientation(new_path)
    rename_map[img_path.name] = new_name
    print(f"Renamed & fixed: {img_path.name} -> {new_name}")

# ---------- 更新 Markdown ----------
md_files = list(MANUSCRIPT_DIR.glob("*.md"))
for md_file in md_files:
    text = md_file.read_text(encoding="utf-8")

    def replace_func(match):
        orig = match.group(1)
        fname = Path(orig).name
        if fname in rename_map:
            new_path = Path(orig).parent / rename_map[fname]
            return f"![]({new_path.as_posix()})"
        return match.group(0)

    text = re.sub(r'!\[.*?\]\((.*?)\)', replace_func, text)
    md_file.write_text(text, encoding="utf-8")
    print(f"Updated Markdown: {md_file}")

# ---------- 生成 EPUB ----------
OUTPUT_FILE.parent.mkdir(exist_ok=True)
md_list = sorted(MANUSCRIPT_DIR.glob("*.md"))

# 確認 metadata.yaml 存在
if not METADATA_FILE.exists():
    print(f"[WARNING] metadata.yaml not found: {METADATA_FILE}. EPUB 會缺少封面/書名資訊。")

cmd = [
    "pandoc",
    *[str(f) for f in md_list],
    "-o", str(OUTPUT_FILE),
    "--resource-path", str(ASSETS_DIR)
]

if METADATA_FILE.exists():
    cmd.extend(["--metadata-file", str(METADATA_FILE)])

print("Generating EPUB...")
try:
    subprocess.run(cmd, check=True)
    print(f"✅ EPUB generated: {OUTPUT_FILE}")
except subprocess.CalledProcessError as e:
    print("❌ EPUB generation failed")
    print(e)
