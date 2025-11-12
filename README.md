# epub_generated.py

**用途**  
快速將 Markdown 與圖片生成 EPUB，適合 Obsidian 或一般 Markdown 專案。

**功能**  
- 自動整理 `assets/` 內圖片檔名，移除非法符號。  
- 自動修正圖片方向（EXIF Orientation）。  
- 更新 `manuscript/` 內 Markdown 連結，對應修正後的圖片檔名。  
- 依檔名排序生成 EPUB。  

**使用方式**  
1. 將 `epub_generated.py` 放在專案根目錄，確保同層有：
   - `manuscript/` 章節 Markdown  
   - `assets/` 圖片  
2. 執行：
```
python epub_generated.py
```

生成的 EPUB 在 output/output.epub。

注意

需安裝 Pandoc。

支援 .jpg、.jpeg、.png 圖片。

Markdown 圖片語法需符合 ![](assets/圖片.jpg) 格式。

不包含任何個人資訊，僅處理檔案名稱與 EPUB 生成。

建議

可將此工具公開於 GitHub，僅需將 manuscript/ 與 assets/ 的實際內容排除即可。

EPUB 生成前，確認 Markdown 與圖片對應正確。

若圖片有 EXIF 旋轉資訊，工具會自動修正方向。
