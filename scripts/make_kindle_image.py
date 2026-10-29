from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageEnhance
import shutil

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
PUBLIC.mkdir(parents=True, exist_ok=True)

# Both layouts are produced. The Kindle browser chooses the matching version
# from its viewport orientation: portrait 600x800 or landscape 800x600.
LAYOUTS = {
    "portrait": {
        "width": 600,
        "raw_height": 1200,
        "crop_top": 330,   # immediately below ClearToFly's header and day selector
        "crop_height": 740,
        "footer_height": 20,
        "tab_height": 40,
    },
    "landscape": {
        "width": 800,
        "raw_height": 1100,
        "crop_top": 510,   # prioritize wind/gusts and the lower aviation weather plots
        "crop_height": 540,
        "footer_height": 20,
        "tab_height": 40,
    },
}
RAW_TEMPLATE = "/tmp/cleartofly-{layout}-day-{day}-raw.png"
BERLIN = ZoneInfo("Europe/Berlin")
now_dt = datetime.now(BERLIN)
now = now_dt.strftime("%d.%m.%Y  %H:%M")

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
def load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()

font_footer = load_font(FONT_PATH, 10)
font_tab = load_font(FONT_BOLD_PATH, 14)
font_tab_small = load_font(FONT_PATH, 13)

labels = []
for day in range(3):
    target = now_dt.date() + timedelta(days=day)
    weekday = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"][target.weekday()]
    date_label = f"{target.day:02d}.{target.month:02d}."
    if day == 0:
        labels.append(f"Heute · {weekday} {date_label}")
    elif day == 1:
        labels.append(f"Morgen · {weekday} {date_label}")
    else:
        labels.append(f"{weekday} {date_label}")


def make_image(layout_name, config, day):
    raw = Path(RAW_TEMPLATE.format(layout=layout_name, day=day))
    if not raw.exists():
        raise SystemExit(f"Screenshot fehlt: {raw}. Der ClearToFly-Aufruf war vermutlich nicht erfolgreich.")

    expected_size = (config["width"], config["raw_height"])
    with Image.open(raw) as source:
        if source.size != expected_size:
            raise SystemExit(
                f"Unerwartete Screenshot-Größe für {layout_name}: {source.size}; erwartet {expected_size}."
            )
        image = source.convert("L")
        x0 = 0
        y0 = config["crop_top"]
        x1 = config["width"]
        y1 = y0 + config["crop_height"]
        if y1 > image.height:
            raise SystemExit(f"Ausschnitt liegt außerhalb des Screenshots: {layout_name}, Tag {day + 1}.")
        chart = image.crop((x0, y0, x1, y1))
        chart = ImageOps.autocontrast(chart, cutoff=0.4)
        chart = ImageEnhance.Contrast(chart).enhance(1.10)

    footer_h = config["footer_height"]
    canvas = Image.new("L", (config["width"], config["crop_height"] + footer_h), 255)
    canvas.paste(chart, (0, 0))
    draw = ImageDraw.Draw(canvas)
    footer_y = config["crop_height"]
    draw.line((0, footer_y, config["width"] - 1, footer_y), fill=0, width=1)
    footer = f"CLEAR TO FLY | ALSFELD | {labels[day]} | STAND: {now}"
    draw.text((5, footer_y + 4), footer, fill=0, font=font_footer)

    output = PUBLIC / f"day-{day}-{layout_name}.png"
    canvas.save(output, format="PNG", optimize=True)
    return output


for layout_name, config in LAYOUTS.items():
    for day in range(3):
        output = make_image(layout_name, config, day)
        print(f"Erstellt: {output} ({config['width']}x{config['crop_height'] + config['footer_height']})")

# Retain current.png for the existing workflow's publication sanity check and
# for compatibility with the first published version.
shutil.copyfile(PUBLIC / "day-0-portrait.png", PUBLIC / "current.png")

# Simple HTML and ES5-compatible JavaScript for the old Kindle browser.
# A wide viewport gets the 800x600-oriented crop; a tall one gets 600x800.
cache_key = now_dt.strftime("%Y%m%d%H%M")
html = f'''<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ClearToFly Alsfeld – Kindle</title>
  <style type="text/css">
    html, body {{ margin: 0; padding: 0; width: 100%; background: #fff; color: #000; font-family: Arial, sans-serif; }}
    body {{ max-width: 800px; margin: 0 auto; overflow: hidden; }}
    #tabs {{ width: 100%; height: 40px; border-bottom: 1px solid #000; overflow: hidden; }}
    .tab {{ float: left; display: block; width: 33.3333%; height: 39px; line-height: 39px; text-align: center; box-sizing: border-box; border-right: 1px solid #777; color: #000; background: #fff; font-size: 13px; text-decoration: none; white-space: nowrap; overflow: hidden; }}
    .tab:last-child {{ border-right: 0; }}
    .tab.active {{ font-weight: bold; border-bottom: 4px solid #000; }}
    #weather {{ display: block; width: 100%; height: auto; border: 0; margin: 0; padding: 0; }}
  </style>
</head>
<body>
  <div id="tabs">
    <a class="tab active" id="tab0" href="#" onclick="showDay(0); return false;">{labels[0]}</a>
    <a class="tab" id="tab1" href="#" onclick="showDay(1); return false;">{labels[1]}</a>
    <a class="tab" id="tab2" href="#" onclick="showDay(2); return false;">{labels[2]}</a>
  </div>
  <img id="weather" src="day-0-portrait.png?build={cache_key}" width="600" height="760" alt="ClearToFly Flugwetter Alsfeld">
  <script type="text/javascript">
    var selectedDay = 0;
    var layoutName = 'portrait';
    function detectLayout() {{
      layoutName = (window.innerWidth > window.innerHeight) ? 'landscape' : 'portrait';
      var image = document.getElementById('weather');
      if (image) image.src = 'day-' + selectedDay + '-' + layoutName + '.png?layout=' + new Date().getTime();
    }}
    function showDay(day) {{
      if (day < 0 || day > 2) return;
      selectedDay = day;
      for (var i = 0; i < 3; i++) {{
        var tab = document.getElementById('tab' + i);
        if (tab) tab.className = (i === day) ? 'tab active' : 'tab';
      }}
      detectLayout();
    }}
    detectLayout();
    if (window.setInterval) window.setInterval(detectLayout, 900000);
  </script>
</body>
</html>
'''
(PUBLIC / "index.html").write_text(html, encoding="utf-8")
print(f"HTML erstellt: {PUBLIC / 'index.html'}")
print("Erzeugt 3 Tagesansichten in Hoch- und Querformat; Bildausschnitte beginnen direkt bei den Wetterdiagrammen.")
