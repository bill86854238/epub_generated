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

# Readmoo 規範
MAX_IMAGE_MB = 3        # 單張圖片最大 3MB
MAX_IMAGE_DIM = 3200    # 長邊需 < 3200px
MAX_CHAPTER_MB = 10     # 單章節圖片總和 < 10MB

# 原本 JPEG 設定（作為初步壓縮）
MAX_WIDTH = 1200
MAX_HEIGHT = 1200
JPEG_QUALITY = 85

# EPUB 封面建議尺寸
COVER_WIDTH = 1600
COVER_HEIGHT = 2560

# ---------- 工具 ----------
def safe_filename(name: str) -> str:
    return re.sub(r'[^\w\.\-一-龥]', '', name)

def fix_image_orientation(img_path: Path):
    try:
        img = Image.open(img_path)
        for orientation in ExifTags.TAGS.keys():
            if ExifTags.TAGS[orientation] == 'Orientation':
                break
        exif = dict(img._getexif().items()) if img._getexif() else {}
        val = exif.get(orientation, 1)
        if val == 3: img = img.rotate(180, expand=True)
        elif val == 6: img = img.rotate(270, expand=True)
        elif val == 8: img = img.rotate(90, expand=True)
        img.save(img_path)
    except Exception:
        pass

def resize_to_max_dimension(img: Image.Image, max_dim=MAX_IMAGE_DIM):
    w, h = img.size
    if max(w, h) <= max_dim:
        return img
    ratio = max_dim / max(w, h)
    return img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

def compress_to_max_size(img: Image.Image, out_path: Path, max_mb=MAX_IMAGE_MB):
    """壓到小於指定 MB，最低品質 40"""
    quality = 90
    tmp = out_path.with_suffix(".tmp.jpg")
    while quality >= 40:
        img.save(tmp, format="JPEG", quality=quality, optimize=True)
        size_mb = tmp.stat().st_size / (1024 * 1024)
        if size_mb <= max_mb:
            break
        quality -= 5
    tmp.replace(out_path)
    print(f"Compressed {out_path.name} -> {size_mb:.2f}MB (quality={quality})")

def process_image_readmoo(img_path: Path):
    """完全符合 Readmoo 規範的處理：方向 → 縮圖3200 → 壓到3MB"""
    try:
        img = Image.open(img_path)
        img = resize_to_max_dimension(img)
        compress_to_max_size(img, img_path)
    except Exception as e:
        print(f"[ERROR] Readmoo process failed: {img_path} ({e})")

def compress_image_basic(img_path: Path):
    """你原本的壓縮流程（初步）"""
    try:
        img = Image.open(img_path)
        w, h = img.size
        scale = min(1, MAX_WIDTH / w, MAX_HEIGHT / h)
        if scale < 1:
            img = img.resize((int(w*scale), int(h*scale)), Image.ANTIALIAS)

        if img_path.suffix.lower() in [".jpg", ".jpeg"]:
            img.save(img_path, quality=JPEG_QUALITY, optimize=True)
        else:
            img.save(img_path, optimize=True)
    except Exception as e:
        print(f"[WARNING] Compress failed: {img_path} ({e})")

def process_cover_image(metadata_file: Path):
    try:
        meta = yaml.safe_load(open(metadata_file, "r", encoding="utf-8"))
        cover_path = Path(meta.get("cover-image", ""))
        if not cover_path.exists():
            return

        img = Image.open(cover_path)
        ratio = img.width / img.height
        target_ratio = COVER_WIDTH / COVER_HEIGHT

        if ratio > target_ratio:
            new_w = COVER_WIDTH; new_h = int(COVER_WIDTH / ratio)
        else:
            new_h = COVER_HEIGHT; new_w = int(COVER_HEIGHT * ratio)

        img = img.resize((new_w, new_h), Image.ANTIALIAS)
        out = cover_path.with_suffix(".jpg")
        img.save(out, quality=JPEG_QUALITY, optimize=True)
        meta["cover-image"] = str(out)
        yaml.safe_dump(meta, open(metadata_file, "w", encoding="utf-8"), allow_unicode=True)
        print(f"Processed cover image: {out}")
    except Exception as e:
        print(f"[WARNING] Failed to process cover image ({e})")

# ---------- 處理封面 ----------
if METADATA_FILE.exists():
    process_cover_image(METADATA_FILE)

# ---------- 處理圖片 ----------
if not ASSETS_DIR.exists():
    print("[ERROR] Assets 資料夾不存在")
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
    compress_image_basic(new_path)        # 初步壓縮
    process_image_readmoo(new_path)       # 完整符合 Readmoo

    rename_map[img_path.name] = new_name
    print(f"Processed: {img_path.name} -> {new_name}")

# ---------- 章節圖片加總壓縮 ----------
def enforce_chapter_limit():
    """自動偵測章節圖片大小總合，必要時再壓縮品質"""
    for md_file in MANUSCRIPT_DIR.glob("*.md"):
        text = md_file.read_text(encoding="utf-8")
        imgs = re.findall(r'!\[.*?\]\((.*?)\)', text)

        total_bytes = 0
        img_paths = []
        for p in imgs:
            path = Path(p)
            if path.exists():
                total_bytes += path.stat().st_size
                img_paths.append(path)

        if total_bytes <= MAX_CHAPTER_MB * 1024 * 1024:
            continue

        print(f"[INFO] {md_file.name} 超過 10MB，開始進行二次壓縮…")

        ratio = (MAX_CHAPTER_MB * 1024 * 1024) / total_bytes
        quality = int(80 * ratio)
        quality = max(35, min(80, quality))

        for img_path in img_paths:
            try:
                img = Image.open(img_path)
                img.save(img_path, format="JPEG", quality=quality, optimize=True)
            except:
                pass

        print(f"[INFO] {md_file.name} 已重新壓縮 (quality={quality}).")

enforce_chapter_limit()

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
    print("[WARNING] metadata.yaml not found...")

cmd = ["pandoc", "-o", str(OUTPUT_FILE)]
if METADATA_FILE.exists():
    cmd.extend(["--metadata-file", str(METADATA_FILE)])
cmd.extend([str(md) for md in md_list])

subprocess.run(cmd)
print(f"EPUB 生成成功: {OUTPUT_FILE}")
