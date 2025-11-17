import os
import re
from pathlib import Path
from PIL import Image, ExifTags
import subprocess
import sys
from datetime import datetime

# ---------- 設定 ----------
MANUSCRIPT_DIR = Path("manuscript")
ASSETS_DIR = Path("assets")

# 使用當前日期時間作為檔名
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_FILE = Path(f"output/book_{timestamp}.epub")

METADATA_FILE = Path("metadata.yaml")
COVER_FILE = ASSETS_DIR / "cover.png"

# ---------- 工具函數 ----------
def safe_filename(name: str) -> str:
    """將檔名轉成安全字元,只保留英數字和點號"""
    # 先嘗試編碼為 ASCII,移除無法編碼的字元
    try:
        name = name.encode('ascii', errors='ignore').decode('ascii')
    except:
        pass
    
    # 移除方括號及其內容
    name = re.sub(r'\[.*?\]', '', name)
    
    # 只保留 ASCII 英數字和點號 (移除連字號、底線等)
    name = re.sub(r'[^a-zA-Z0-9\.]', '', name)
    
    # 如果檔名變空了,使用時間戳
    if not name or name == '.':
        from datetime import datetime
        name = datetime.now().strftime('%Y%m%d%H%M%S')
    
    return name

def fix_image_orientation(img_path: Path):
    """修正圖片方向並壓縮尺寸"""
    try:
        img = Image.open(img_path)
        
        # 修正 EXIF 方向
        try:
            for orientation in ExifTags.TAGS.keys():
                if ExifTags.TAGS[orientation] == 'Orientation':
                    break
            exif = dict(img._getexif().items()) if img._getexif() else {}
            val = exif.get(orientation, 1)
            if val == 3:
                img = img.rotate(180, expand=True)
            elif val == 6:
                img = img.rotate(270, expand=True)
            elif val == 8:
                img = img.rotate(90, expand=True)
        except:
            pass
        
        # 檢查圖片尺寸並壓縮
        width, height = img.size
        total_pixels = width * height
        max_pixels = 5600000  # Readmoo 限制
        
        if total_pixels > max_pixels:
            # 計算縮放比例
            scale = (max_pixels / total_pixels) ** 0.5
            new_width = int(width * scale)
            new_height = int(height * scale)
            
            print(f"    壓縮: {width}x{height} → {new_width}x{new_height}")
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # 轉換為 RGB (移除 alpha 通道)
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background
        
        # 儲存為高品質 JPEG
        img.save(img_path, 'JPEG', quality=85, optimize=True)
        
    except Exception as e:
        print(f"    ⚠️  處理失敗: {e}")

# ---------- 步驟1: 建立圖片改名對照表 ----------
if not ASSETS_DIR.exists():
    print(f"[ERROR] Assets 資料夾不存在: {ASSETS_DIR}")
    sys.exit(1)

print("📸 處理圖片檔案...")
rename_map = {}  # 舊檔名 -> 新檔名
existing_images = {}  # 新檔名 -> 完整路徑

for img_path in ASSETS_DIR.iterdir():
    if img_path.suffix.lower() not in [".jpg", ".jpeg", ".png"]:
        continue
    
    try:
        old_name = img_path.name
        new_name = safe_filename(img_path.stem) + img_path.suffix.lower()
        new_path = ASSETS_DIR / new_name
        
        # 避免檔名衝突
        counter = 1
        while new_path.exists() and new_path != img_path:
            new_name = f"{safe_filename(img_path.stem)}_{counter}{img_path.suffix.lower()}"
            new_path = ASSETS_DIR / new_name
            counter += 1
        
        # 改名
        if img_path != new_path:
            img_path.rename(new_path)
            print(f"  ✓ {old_name} → {new_name}")
        
        fix_image_orientation(new_path)
        
        # 記錄對照
        rename_map[old_name] = new_name
        existing_images[new_name] = new_path
        
    except Exception as e:
        print(f"  ⚠️  無法處理 {img_path.name}: {e}")

print(f"\n✅ 處理了 {len(rename_map)} 個圖片檔案\n")

# ---------- 步驟2: 強制替換 Markdown 中的所有圖片連結 ----------
print("📝 更新 Markdown 檔案...")
md_files = list(MANUSCRIPT_DIR.glob("*.md"))
all_referenced_images = set()

for md_file in md_files:
    text = md_file.read_text(encoding="utf-8")
    original_text = text
    replacements = []
    
    def replace_func(match):
        alt_text = match.group(1)
        orig_path = match.group(2)
        
        # 提取原始檔名
        orig_filename = Path(orig_path).name
        
        # 清理檔名:移除方括號內容和特殊字元
        clean_name = safe_filename(Path(orig_path).stem) + Path(orig_path).suffix.lower()
        
        # 記錄引用的圖片
        all_referenced_images.add(clean_name)
        
        # 記錄替換
        if orig_filename != clean_name:
            replacements.append(f"    {orig_filename} → {clean_name}")
        
        return f"![{alt_text}]({clean_name})"
    
    # 替換所有圖片連結
    text = re.sub(r'!\[(.*?)\]\((.*?)\)', replace_func, text)
    
    if text != original_text:
        md_file.write_text(text, encoding="utf-8")
        print(f"  ✓ {md_file.name}")
        if replacements:
            for r in replacements[:3]:  # 只顯示前3個
                print(r)
            if len(replacements) > 3:
                print(f"    ... 還有 {len(replacements)-3} 個替換")
    else:
        print(f"    {md_file.name} (無變更)")

# 檢查缺失的圖片
print(f"\n🔍 檢查圖片完整性...")
missing_images = []
for img_name in all_referenced_images:
    if not (ASSETS_DIR / img_name).exists():
        missing_images.append(img_name)

if missing_images:
    print(f"  ⚠️  找不到以下 {len(missing_images)} 張圖片:")
    for img in missing_images:
        print(f"    ✗ {img}")
    print(f"  提示: 這些圖片會在 EPUB 中顯示為空白\n")
else:
    print(f"  ✓ 所有圖片都存在\n")

print(f"✅ 完成 Markdown 更新\n")

# ---------- 步驟3: 生成 EPUB ----------
OUTPUT_FILE.parent.mkdir(exist_ok=True)
md_list = sorted(MANUSCRIPT_DIR.glob("*.md"))

# 取得絕對路徑
assets_abs = ASSETS_DIR.resolve()
manuscript_abs = MANUSCRIPT_DIR.resolve()

cmd = [
    "pandoc",
    *[str(f) for f in md_list],
    "-o", str(OUTPUT_FILE),
    "--resource-path", f"{manuscript_abs};{assets_abs}",  # Windows 用分號
]

if METADATA_FILE.exists():
    cmd.extend(["--metadata-file", str(METADATA_FILE)])

# 只在封面存在時才加入
if COVER_FILE.exists():
    cmd.extend(["--epub-cover-image", str(COVER_FILE)])
else:
    print(f"⚠️  封面不存在: {COVER_FILE}")

print("📚 生成 EPUB...")
print(f"   資源路徑: {manuscript_abs};{assets_abs}")
try:
    result = subprocess.run(
        cmd, 
        check=True, 
        capture_output=True, 
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    if result.stderr:
        print("\n⚠️  警告訊息:")
        for line in result.stderr.split('\n')[:5]:  # 只顯示前5行
            if line.strip():
                print(f"   {line}")
    print(f"\n✅ EPUB 生成成功: {OUTPUT_FILE}\n")
except subprocess.CalledProcessError as e:
    print("❌ EPUB 生成失敗\n")
    if e.stderr:
        print("錯誤訊息:")
        print(e.stderr)
    sys.exit(1)
