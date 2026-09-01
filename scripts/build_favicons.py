#!/usr/bin/env python3
"""從 favicon.svg 產生 Google 讀得懂的點陣圖示（favicon.ico 與 favicon-96.png）。

為什麼需要這支：
  Google 的 favicon 支援格式白紙黑字只有 BMP／GIF／ICO／JPEG／PNG／PPM／TIFF，
  **沒有 SVG**。本站原本只宣告 favicon.svg，而 /favicon.ico 雖然回 200，
  Content-Type 卻是 text/html（那是 Cloudflare Pages 的 404 fallback，不是圖檔），
  等於搜尋結果上抓不到合格圖示。2026-09-01 由 SEO 週報排程查出。

為什麼用 headless Chrome 而不裝套件：
  本專案的 CI 只有 Python，不想為了一次性的圖示多一個相依。這個做法照抄
  flight-deck/tools/icons/build.js，那支已經在 Windows 上跑順過。

  ⚠️ 不要用 `--window-size=N,N` ＋ `--screenshot`。Windows 版 Chrome 會把視窗寬度
  夾在 500px 下限，高度還要再扣掉外框，小尺寸圖會整片白。改法是把 SVG 以 data URI
  餵給 <img>，用 canvas 畫成剛好 N×N 再 toDataURL，靠 --dump-dom 把 base64 帶回來。
  尺寸由 canvas 決定，與視窗無關。

  這支是**手動執行**的，不進 CI（CI 沒有 Chrome）。改了 favicon.svg 才需要重跑：
      python -X utf8 scripts/build_favicons.py

產出（都要一起 commit，並確認在 daily_update.yml 的 git add 白名單裡）：
  favicon.ico     16／32／48 三尺寸，給 /favicon.ico 這個慣例路徑
  favicon-96.png  96×96，HTML 裡宣告用（48 的倍數）
"""
import base64
import io
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SVG = ROOT / "favicon.svg"
ICO = ROOT / "favicon.ico"
PNG96 = ROOT / "favicon-96.png"

ICO_SIZES = (16, 32, 48)


def find_chrome():
    if os.environ.get("CHROME"):
        return os.environ["CHROME"]
    candidates = [
        r"C:/Program Files/Google/Chrome/Application/chrome.exe",
        r"C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
        r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
        r"C:/Program Files/Microsoft/Edge/Application/msedge.exe",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
    ]
    for c in candidates:
        if pathlib.Path(c).exists():
            return c
    found = shutil.which("chrome") or shutil.which("chromium") or shutil.which("msedge")
    if found:
        return found
    sys.exit("找不到 Chrome／Edge，請用環境變數 CHROME 指定執行檔路徑。")


def rasterize(svg_text, size, chrome, tmpdir):
    """把 SVG 光柵化成 size×size 的 PNG bytes。"""
    svg_b64 = base64.b64encode(
        svg_text[svg_text.index("<svg"):].encode("utf-8")
    ).decode("ascii")
    page = (
        '<!doctype html><meta charset="utf-8"><body><div id="out"></div><script>\n'
        "const img = new Image();\n"
        "img.onload = () => {\n"
        "  const c = document.createElement('canvas');\n"
        f"  c.width = c.height = {size};\n"
        "  const g = c.getContext('2d');\n"
        "  g.imageSmoothingEnabled = true;\n"
        "  g.imageSmoothingQuality = 'high';\n"
        f"  g.drawImage(img, 0, 0, {size}, {size});\n"
        "  document.getElementById('out').textContent = c.toDataURL('image/png');\n"
        "};\n"
        "img.onerror = () => { document.getElementById('out').textContent = 'RASTERIZE-ERROR'; };\n"
        f"img.src = 'data:image/svg+xml;base64,{svg_b64}';\n"
        "</scr" + "ipt></body>"
    )
    wrapper = pathlib.Path(tmpdir) / f"wrap-{size}.html"
    wrapper.write_text(page, encoding="utf-8")

    dom = subprocess.run(
        [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            f"--user-data-dir={pathlib.Path(tmpdir) / ('profile-' + str(size))}",
            "--virtual-time-budget=5000",
            "--dump-dom",
            "file:///" + str(wrapper).replace("\\", "/"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout

    hit = re.search(r"data:image/png;base64,([A-Za-z0-9+/=]+)", dom or "")
    if not hit:
        sys.exit(f"光柵化 {size}px 失敗，Chrome 沒有回傳 PNG。")
    return base64.b64decode(hit.group(1))


def selfcheck(png_bytes, size, label):
    """真的看像素。檔案大小擋不住『半張白圖』，一定要解碼確認。

    flight-deck 2026-08-20 產過一張半白的 icon-192，它有 2310 bytes，
    比正常的 32px 還大，只看檔案大小完全抓不到。
    """
    from PIL import Image

    im = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    if im.size != (size, size):
        sys.exit(f"{label}：尺寸是 {im.size}，應為 {(size, size)}。")

    px = im.load()
    opaque = 0
    colours = set()
    for y in range(size):
        for x in range(size):
            r, g, b, a = px[x, y]
            if a > 16:
                opaque += 1
                colours.add((r // 32, g // 32, b // 32))

    total = size * size
    if opaque < total * 0.15:
        sys.exit(f"{label}：只有 {opaque}/{total} 個不透明像素，圖幾乎是空的。")
    if len(colours) < 2:
        sys.exit(f"{label}：整張只有 {len(colours)} 種顏色，可能是純色塊。")
    return opaque, len(colours)


def main():
    if not SVG.exists():
        sys.exit(f"找不到 {SVG}")
    svg_text = SVG.read_text(encoding="utf-8")
    chrome = find_chrome()
    print(f"瀏覽器：{chrome}")

    from PIL import Image

    with tempfile.TemporaryDirectory() as tmpdir:
        frames = []
        for size in ICO_SIZES:
            data = rasterize(svg_text, size, chrome, tmpdir)
            opaque, colours = selfcheck(data, size, f"{size}px")
            print(f"  {size:>3}px  不透明 {opaque:>5} 像素、{colours} 種色調  ✓")
            frames.append(Image.open(io.BytesIO(data)).convert("RGBA"))

        data96 = rasterize(svg_text, 96, chrome, tmpdir)
        opaque, colours = selfcheck(data96, 96, "96px")
        print(f"   96px  不透明 {opaque:>5} 像素、{colours} 種色調  ✓")
        PNG96.write_bytes(data96)

        # 多尺寸 ICO：以最大張為底，sizes 帶入其餘尺寸，Pillow 會自己縮。
        frames[-1].save(ICO, format="ICO", sizes=[(s, s) for s in ICO_SIZES])

    print(f"\n產出：")
    print(f"  {ICO.name}  {ICO.stat().st_size} bytes（{'／'.join(str(s) for s in ICO_SIZES)}）")
    print(f"  {PNG96.name}  {PNG96.stat().st_size} bytes")
    print("\n記得：兩個檔案都要在 daily_update.yml 的 git add 白名單裡，否則 CI 不會帶上線。")


if __name__ == "__main__":
    main()
