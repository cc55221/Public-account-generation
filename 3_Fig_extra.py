# save_figures_from_pdf.py
# pip install pymupdf pillow
import fitz  # PyMuPDF
import re
from pathlib import Path
import argparse

CAPTION_RE = re.compile(r'^\s*(Fig\.|Figure)\s*\d+[\s:.,-]?', re.IGNORECASE)

def rect_union(rects):
    r = fitz.Rect(rects[0])
    for rr in rects[1:]:
        r |= fitz.Rect(rr)
    return r

def extract_figures(pdf_path: Path, dpi: int = 300, prefix: str = "Fig"):
    doc = fitz.open(pdf_path)
    save_dir = Path(".")  # 当前文件夹
    total = 0

    for pno, page in enumerate(doc, start=1):
        # 1) 找图注块
        captions = []
        for x0, y0, x1, y1, text, *_ in page.get_text("blocks"):
            txt = (text or "").strip()
            if CAPTION_RE.search(txt):
                captions.append({"bbox": fitz.Rect(x0, y0, x1, y1), "text": txt})

        if not captions:
            continue

        # 2) 页面里的图像块（rawdict 中 type=1）
        raw = page.get_text("rawdict")
        image_blocks = [fitz.Rect(b["bbox"]) for b in raw["blocks"] if b["type"] == 1]

        for idx, cap in enumerate(captions, start=1):
            cap_box = cap["bbox"]
            margin_x, margin_y = 6, 6

            # 3) 在图注上方寻找图像块（常见：子图并列）
            candidates = []
            for r in image_blocks:
                if r.y1 <= cap_box.y0:  # 必须位于图注之上
                    horiz_overlap = not (r.x1 < cap_box.x0 or r.x0 > cap_box.x1)
                    wide = (r.width > page.rect.width * 0.25)
                    near = (cap_box.y0 - r.y1) < page.rect.height * 0.35
                    if (horiz_overlap or wide) and near:
                        candidates.append(r)

            if candidates:
                crop_rect = rect_union(candidates)
                crop_rect.x0 = max(page.rect.x0, crop_rect.x0 - margin_x)
                crop_rect.y0 = max(page.rect.y0, crop_rect.y0 - margin_y)
                crop_rect.x1 = min(page.rect.x1, crop_rect.x1 + margin_x)
                crop_rect.y1 = min(cap_box.y0 - 2, crop_rect.y1 + margin_y)  # 保持在图注之上
            else:
                # 4) 回退策略：从图注往上取一段矩形
                h = min(page.rect.height * 0.38, max(120, cap_box.height * 12))
                crop_rect = fitz.Rect(page.rect.x0 + margin_x,
                                      max(page.rect.y0, cap_box.y0 - h),
                                      page.rect.x1 - margin_x,
                                      cap_box.y0 - 2)

            # 5) 导出为 PNG（保存在当前目录）
            pix = page.get_pixmap(clip=crop_rect, dpi=dpi, alpha=False)
            out_name = f"{prefix}_p{pno:02d}_f{idx:02d}.png"
            out_path = save_dir / out_name
            pix.save(out_path.as_posix())
            total += 1
            print(f"Saved: {out_path}")

    print(f"Done. Saved {total} figure crops to: {Path('.').resolve()}")

from typing import Optional

def pick_latest_pdf_in_cwd() -> Optional[Path]:
    pdfs = list(Path(".").glob("*.pdf"))
    if not pdfs:
        return None
    pdfs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return pdfs[0]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Crop all figures above 'Fig.'/'Figure' captions from a PDF."
    )
    # 把 pdf 改为可选
    parser.add_argument("pdf", nargs="?", type=str,
                        help="Path to the PDF file (optional if a PDF exists in current folder)")
    parser.add_argument("--dpi", type=int, default=300, help="Output DPI (default: 300)")
    parser.add_argument("--prefix", type=str, default="Fig", help="Filename prefix (default: Fig)")
    args = parser.parse_args()

    pdf_path = Path(args.pdf) if args.pdf else pick_latest_pdf_in_cwd()
    if not pdf_path or not pdf_path.exists():
        raise SystemExit("No PDF specified and none found in current folder.")

    extract_figures(pdf_path, dpi=args.dpi, prefix=args.prefix)
