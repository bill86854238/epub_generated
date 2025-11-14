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

# 圖片壓縮設定
MAX_WIDTH = 1200    # 最大寬度
MAX_HEIGHT = 1200   # 最大高度
JPEG_QUALITY = 85   # JPEG 壓縮品質 (0-100)

# EPUB 封面建議尺寸
COVER_WIDTH = 1600
COVER_HEIGHT = 2560

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

def compress_image(img_path: Path, max_w=MAX_WIDTH, max_h=MAX_HEIGHT):
    """批量壓縮並限制尺寸"""
    try:
        img = Image.open(img_path)
        w, h = img.size

        # 計算縮放比例
        scale = min(1, max_w / w, max_h / h)
        if scale < 1:
            new_size = (int(w*scale), int(h*scale))
            img = img.resize(new_size, Image.ANTIALIAS)

        # 保存 JPEG 或 PNG
        if img_path.suffix.lower() in [".jpg", ".jpeg"]:
            img.save(img_path, quality=JPEG_QUALITY, optimize=True)
        else:
            img.save(img_path, optimize=True)
    except Exception as e:
        print(f"[WARNING] Compress failed: {img_path} ({e})")

def process_cover_image(metadata_file: Path):
    """自動縮放封面圖片到 EPUB 推薦尺寸"""
    try:
        with open(metadata_file, "r", encoding="utf-8") as f:
            meta = yaml.safe_load(f)
        cover_path = Path(meta.get("cover-image", ""))
        if cover_path.exists():
            img = Image.open(cover_path)
            img_ratio = img.width / img.height
            target_ratio = COVER_WIDTH / COVER_HEIGHT

            # 計算縮放尺寸，保留長寬比
            if img_ratio > target_ratio:
                # 太寬 -> 寬度限制
                new_w = COVER_WIDTH
                new_h = int(COVER_WIDTH / img_ratio)
            else:
                # 太高 -> 高度限制
                new_h = COVER_HEIGHT
                new_w = int(COVER_HEIGHT * img_ratio)

            img = img.resize((new_w, new_h), Image.ANTIALIAS)
            # 強制轉成 JPEG
            cover_out = cover_path.with_suffix(".jpg")
            img.save(cover_out, quality=JPEG_QUALITY, optimize=True)
            meta["cover-image"] = str(cover_out)
            with open(metadata_file, "w", encoding="utf-8") as f:
                yaml.safe_dump(meta, f, allow_unicode=True)
            print(f"Processed cover image: {cover_out}")
        else:
            print(f"[WARNING] Cover image not found: {cover_path}")
    except Exception as e:
        print(f"[WARNING] Failed to process cover image ({e})")

# ---------- 處理封面 ----------
if METADATA_FILE.exists():
    process_cover_image(METADATA_FILE)

# ---------- 處理一般圖片 ----------
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
    compress_image(new_path)
    rename_map[img_path.name] = new_name
    print(f"Processed: {img_path.name} -> {new_name}")

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
