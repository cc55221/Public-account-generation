# -*- coding: utf-8 -*-
# screenshot_fullpage_nocli.py
# 整页截图为一张 PNG（优先 full_page，一旦失败自动滚动拼接）

import asyncio
from pathlib import Path
from datetime import datetime
from typing import List

from playwright.async_api import async_playwright, TimeoutError as PWTimeout
from PIL import Image

# ===== 只需改这里（如要换页面/参数）=====
URL = "https://www.mdnice.com/preview/fc506f24719347698744d5108bd38612"
OUTDIR = "."
WIDTH = 800          # 页面宽度
DEVICE_SCALE = 2      # 像素比例（清晰度）
VIEWPORT_H = 1500     # 备用拼接时的视口高度
# =====================================

async def try_fullpage(page, outpath: Path) -> bool:
    try:
        await page.screenshot(path=str(outpath), full_page=True)
        return True
    except Exception as e:
        print(f"[full_page] 失败，切换拼接方案：{e}")
        return False

async def stitch_fullpage(page, outpath: Path):
    # 获取页面总高
    total_h = await page.evaluate("() => Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)")
    # 逐段截图
    chunks: List[Image.Image] = []
    y = 0
    idx = 0
    while y < total_h:
        idx += 1
        await page.evaluate("y => window.scrollTo(0, y)", y)
        await page.wait_for_timeout(80)
        png_path = outpath.with_name(f"{outpath.stem}._part{idx:03d}.png")
        await page.screenshot(path=str(png_path), clip={
            "x": 0, "y": y, "width": WIDTH, "height": min(VIEWPORT_H, total_h - y)
        })
        img = Image.open(png_path)
        chunks.append(img.copy())
        img.close()
        png_path.unlink(missing_ok=True)
        y += VIEWPORT_H

    # 拼接
    total_height = sum(im.height for im in chunks)
    total_width = max(im.width for im in chunks)
    canvas = Image.new("RGB", (total_width, total_height), (255, 255, 255))
    cur_y = 0
    for im in chunks:
        canvas.paste(im, (0, cur_y))
        cur_y += im.height
        im.close()
    canvas.save(outpath)
    print(f"[stitch] 已拼接 {len(chunks)} 段 -> {outpath.name}")

async def main():
    outdir = Path(OUTDIR); outdir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    outfile = outdir / f"fullpage_{ts}.png"

    async with async_playwright() as pw:
        # 优先系统 Chrome；失败用内置 chromium
        try:
            browser = await pw.chromium.launch(channel="chrome", headless=True)
        except Exception:
            browser = await pw.chromium.launch(headless=True)

        context = await browser.new_context(
            viewport={"width": WIDTH, "height": VIEWPORT_H},
            device_scale_factor=DEVICE_SCALE,
        )
        page = await context.new_page()

        await page.goto(URL, wait_until="domcontentloaded")
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except PWTimeout:
            pass
        await page.wait_for_timeout(300)

        # 先尝试 full_page
        ok = await try_fullpage(page, outfile)
        if not ok:
            await stitch_fullpage(page, outfile)

        await browser.close()
        print(f"完成：{outfile.resolve()}")

if __name__ == "__main__":
    asyncio.run(main())
