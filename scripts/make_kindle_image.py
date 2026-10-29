from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageEnhance

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
RAW = Path("/tmp/cleartofly-raw.png")

if not RAW.exists():
    raise SystemExit("Screenshot fehlt; der ClearToFly-Aufruf war vermutlich nicht erfolgreich.")

# Kindle Touch (D01200) is 600 x 800 pixels. Reserve a small footer for a
# visible freshness timestamp, leaving a 600 x 720 capture area for the page.
W, VIEW_H, FOOTER_H = 600, 720, 20
with Image.open(RAW) as source:
    image = source.convert("L")
    if image.size != (W, VIEW_H):
        image = ImageOps.fit(image, (W, VIEW_H), method=Image.Resampling.LANCZOS)
    image = ImageOps.autocontrast(image, cutoff=0.5)
    image = ImageEnhance.Contrast(image).enhance(1.12)

canvas = Image.new("L", (W, VIEW_H + FOOTER_H), 255)
canvas.paste(image, (0, 0))
draw = ImageDraw.Draw(canvas)
draw.line((0, VIEW_H, W - 1, VIEW_H), fill=0, width=1)

font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
try:
    font = ImageFont.truetype(font_path, 11)
except OSError:
    font = ImageFont.load_default()

now = datetime.now(ZoneInfo("Europe/Berlin")).strftime("%d.%m.%Y  %H:%M")
footer = f"CLEAR TO FLY  |  ALSFELD  |  STAND: {now}"
draw.text((6, VIEW_H + 3), footer, fill=0, font=font)

PUBLIC.mkdir(parents=True, exist_ok=True)
canvas.save(PUBLIC / "current.png", format="PNG", optimize=True)

# The query string produced by Date.now() in the tiny ES5 script prevents the
# old Kindle browser from reusing a cached image after its next refresh.
html = f'''<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="900">
  <title>ClearToFly Alsfeld – Kindle</title>
  <style>
    html, body {{ margin: 0; padding: 0; width: 100%; background: #fff; }}
    img {{ display: block; width: 100%; max-width: 600px; height: auto; margin: 0 auto; border: 0; }}
  </style>
</head>
<body>
  <img id="weather" src="current.png?build={now.replace(' ', '_').replace(':', '')}" width="600" height="740" alt="ClearToFly Flugwetter Alsfeld">
  <script type="text/javascript">
    (function () {{
      var image = document.getElementById('weather');
      function refreshImage() {{ image.src = 'current.png?cache=' + new Date().getTime(); }}
      refreshImage();
      if (window.setInterval) window.setInterval(refreshImage, 900000);
    }}());
  </script>
</body>
</html>
'''
(PUBLIC / "index.html").write_text(html, encoding="utf-8")
print(f"Kindle-Bild erstellt: {PUBLIC / 'current.png'} ({canvas.width}x{canvas.height})")
print(f"Aktualisiert: {now} Europe/Berlin")
