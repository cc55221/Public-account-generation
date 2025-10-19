# -*- coding: utf-8 -*-
"""
pdf_first_page_to_png.py
在当前文件夹中查找“最新修改”的 PDF，截取首页并保存为 PNG（保存在当前文件夹）。
依赖：pip install pymupdf
用法：
  直接运行（默认 200 DPI）：
      python pdf_first_page_to_png.py
  指定 DPI（越大越清晰，文件也越大）：
      python pdf_first_page_to_png.py --dpi 300
  指定要处理的 PDF 文件名（可选；若不指定，则选取当前目录中最近修改的一个 PDF）:
      python pdf_first_page_to_png.py --pdf your_file.pdf
"""

import argparse
from pathlib import Path
import sys

try:
    import fitz  # PyMuPDF
except Exception as e:
    print("请先安装依赖：pip install pymupdf")
    raise

def pick_latest_pdf(cwd: Path) -> Path | None:
    pdfs = sorted(cwd.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
    return pdfs[0] if pdfs else None

def render_first_page_to_png(pdf_path: Path, dpi: int) -> Path:
    doc = fitz.open(pdf_path)
    if doc.page_count == 0:
        raise RuntimeError(f"{pdf_path.name} 没有页面。")

    page = doc.load_page(0)  # 首页
    # DPI -> 缩放矩阵（72dpi 为 1:1）
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)  # 去掉透明背景，得到白底 PNG

    out_path = pdf_path.with_name(f"{pdf_path.stem}_p1_{dpi}dpi.png")
    pix.save(out_path.as_posix())
    doc.close()
    return out_path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dpi", type=int, default=200, help="输出 PNG 的分辨率（DPI），默认 200")
    parser.add_argument("--pdf", type=str, default=None, help="指定要处理的 PDF 文件名（可选）")
    args = parser.parse_args()

    cwd = Path(".")
    if args.pdf:
        pdf_path = Path(args.pdf)
        if not pdf_path.exists():
            print(f"未找到指定文件：{pdf_path}")
            sys.exit(1)
    else:
        pdf_path = pick_latest_pdf(cwd)
        if pdf_path is None:
            print("当前文件夹未找到任何 PDF。")
            sys.exit(1)

    try:
        out = render_first_page_to_png(pdf_path, dpi=args.dpi)
        print(f"已保存：{out.resolve()}")
    except Exception as e:
        print(f"处理失败：{e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
