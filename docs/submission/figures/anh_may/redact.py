#!/usr/bin/env python3
"""Hides the real position in the app screenshots before they go into the report (coordinates boxed, map blurred).
  python redact.py   (reads raw/*.png, writes *.png next to this file)"""
import json, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).parent
BOXES = json.loads((HERE / "boxes.json").read_text())
FONT = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"

for name, spec in BOXES.items():
    im = Image.open(HERE / "raw" / f"{name}.png").convert("RGB")
    for x0, y0, x1, y1 in spec.get("blur", []):
        reg = im.crop((x0, y0, x1, y1)).filter(ImageFilter.GaussianBlur(28))
        im.paste(reg, (x0, y0))
        d = ImageDraw.Draw(im)
        f = ImageFont.truetype(FONT, 40)
        d.rounded_rectangle((x0 + 40, (y0 + y1) // 2 - 45, x1 - 40, (y0 + y1) // 2 + 45), 20, fill=(20, 27, 51))
        d.text(((x0 + x1) // 2, (y0 + y1) // 2), "Bản đồ đã làm mờ (riêng tư)", font=f, fill="white", anchor="mm")
    d = ImageDraw.Draw(im)
    for x0, y0, x1, y1 in spec.get("box", []):
        f = ImageFont.truetype(FONT, max(26, (y1 - y0) // 2))
        d.rounded_rectangle((x0, y0, x1, y1), 14, fill=tuple(spec.get("fill", [38, 48, 85])), outline=(150, 160, 190), width=2)
        d.text(((x0 + x1) // 2, (y0 + y1) // 2), "tọa độ đã che", font=f, fill=tuple(spec.get("ink", [220, 225, 240] if spec.get("fill", [0])[0] < 128 else [70, 80, 110])), anchor="mm")
    im.save(HERE / f"{name}.png")
    print(name, im.size)
