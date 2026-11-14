#!/usr/bin/env python3
"""Joins the redacted screenshots into ../anh_may.jpg (Fold7 a-c, TCL d-f). Run redact.py first.
  python compose.py"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
HERE = Path(__file__).parent
F = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
items = [("f7_chat", "a"), ("f7_settings", "b"), ("f7_card", "c"), ("tcl_chat", "d"), ("tcl_settings", "e"), ("tcl_location", "f")]
H = 1400; gap = 24; ims = []
for n, l in items:
    im = Image.open(HERE / f"{n}.png").convert("RGB")
    # drop the status bar (time, notifications) and the gesture bar
    sb = int(im.height * 0.035); im = im.crop((0, sb, im.width, im.height - int(im.height * 0.02)))
    im = im.resize((int(im.width * H / im.height), H))
    d = ImageDraw.Draw(im); f = ImageFont.truetype(F, 46)
    d.rounded_rectangle((14, 14, 84, 84), 16, fill=(11, 60, 120)); d.text((49, 49), l, font=f, fill="white", anchor="mm")
    ims.append(im)
W = sum(i.width for i in ims) + gap * (len(ims) - 1) + gap * 2  # extra gap between the two phones
c = Image.new("RGB", (W, H), "white"); x = 0
for k, im in enumerate(ims):
    c.paste(im, (x, 0)); x += im.width + gap + (gap * 2 if k == 2 else 0)
c.save(HERE.parent / "anh_may.jpg", quality=88); print(c.size)
