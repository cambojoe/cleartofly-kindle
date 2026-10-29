from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageEnhance, ImageChops
import shutil

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
PUBLIC.mkdir(parents=True, exist_ok=True)

WIDTH = 600
CONTENT_HEIGHT = 740
FOOTER_HEIGHT = 20
TOTAL_IMAGE_HEIGHT = CONTENT_HEIGHT + FOOTER_HEIGHT
RAW_TEMPLATE = "/tmp/cleartofly-day-{day}-section-{section}.png"
BERLIN = ZoneInfo("Europe/Berlin")
now_dt = datetime.now(BERLIN)
now = now_dt.strftime("%d.%m.%Y  %H:%M")

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

PAGE_SECTIONS = [
    [
        ("temperature", "Temperature"),
        ("wind", "Wind"),
        ("crosswind", "Crosswind"),
        ("visibility", "Visibility"),
    ],
    [
        ("runway-wind", "Runway wind"),
        ("cloud-cover", "Cloud cover"),
        ("pressure", "Pressure"),
        ("sun-elevation", "Sun elevation"),
    ],
]


def load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


font_footer = load_font(FONT_PATH, 10)


def date_label(day):
    target = now_dt.date() + timedelta(days=day)
    weekdays = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    base = f"{weekdays[target.weekday()]} {target.day:02d}.{target.month:02d}."
    if day == 0:
        return f"HEUTE · {base}"
    if day == 1:
        return f"MORGEN · {base}"
    return f"ÜBERMORGEN · {base}"


labels = [date_label(day) for day in range(3)]


def load_panel(day, section, label):
    raw_path = Path(RAW_TEMPLATE.format(day=day, section=section))
    if not raw_path.exists():
        raise SystemExit(f"Screenshot für „{label}“ fehlt: {raw_path}. Der Workflow wird nicht veröffentlicht.")
    with Image.open(raw_path) as source:
        if source.width < 250 or source.height < 60:
            raise SystemExit(f"Screenshot für „{label}“ ist unerwartet klein: {source.width}x{source.height}.")
        image = source.convert("L")
        # Trim only the empty outer white margin while preserving a small safety border.
        difference = ImageChops.difference(image, Image.new("L", image.size, 255))
        mask = difference.point(lambda value: 255 if value >= 10 else 0)
        bbox = mask.getbbox()
        if bbox:
            left, top, right, bottom = bbox
            pad = 7
            bbox = (max(0, left - pad), max(0, top - pad), min(image.width, right + pad), min(image.height, bottom + pad))
            cropped = image.crop(bbox)
            # Use the crop only when it keeps most of the original graph width.
            if cropped.width >= image.width * 0.78 and cropped.height >= image.height * 0.55:
                image = cropped
        image = ImageOps.autocontrast(image, cutoff=0.4)
        image = ImageEnhance.Contrast(image).enhance(1.08)
        return image.copy()


def compose_page(day, page):
    panels = [load_panel(day, key, label) for key, label in PAGE_SECTIONS[page]]

    # Normalize panel widths to Kindle width before calculating a single fit scale.
    normalized = []
    for image in panels:
        new_height = max(1, round(image.height * WIDTH / image.width))
        normalized.append(image.resize((WIDTH, new_height), Image.Resampling.LANCZOS))

    gap = 4
    total_gaps = gap * (len(normalized) - 1)
    total_height = sum(image.height for image in normalized) + total_gaps
    available = CONTENT_HEIGHT
    scale = min(1.0, available / max(1, total_height))
    final_panels = []
    for image in normalized:
        new_w = max(1, round(image.width * scale))
        new_h = max(1, round(image.height * scale))
        final_panels.append(image.resize((new_w, new_h), Image.Resampling.LANCZOS) if scale < 0.999 else image)

    final_gap = max(2, round(gap * scale))
    used_height = sum(image.height for image in final_panels) + final_gap * (len(final_panels) - 1)
    if used_height > CONTENT_HEIGHT:
        # Account for integer rounding by shrinking all panels very slightly.
        extra_scale = (CONTENT_HEIGHT - final_gap * (len(final_panels) - 1)) / max(1, sum(image.height for image in final_panels))
        revised = []
        for image in final_panels:
            revised.append(image.resize((max(1, round(image.width * extra_scale)), max(1, round(image.height * extra_scale))), Image.Resampling.LANCZOS))
        final_panels = revised
        used_height = sum(image.height for image in final_panels) + final_gap * (len(final_panels) - 1)

    canvas = Image.new("L", (WIDTH, TOTAL_IMAGE_HEIGHT), 255)
    y = max(0, (CONTENT_HEIGHT - used_height) // 2) if used_height < CONTENT_HEIGHT else 0
    for index, image in enumerate(final_panels):
        x = (WIDTH - image.width) // 2
        canvas.paste(image, (x, y))
        y += image.height
        if index != len(final_panels) - 1:
            draw_gap = ImageDraw.Draw(canvas)
            draw_gap.line((12, y + final_gap // 2, WIDTH - 13, y + final_gap // 2), fill=180, width=1)
            y += final_gap

    draw = ImageDraw.Draw(canvas)
    footer_y = CONTENT_HEIGHT
    draw.line((0, footer_y, WIDTH - 1, footer_y), fill=0, width=1)
    if page == 0:
        page_name = "PAGE 1: TEMP / WIND / CROSSWIND / VISIBILITY"
    else:
        page_name = "PAGE 2: RUNWAY / CLOUD / PRESSURE / SUN"
    footer = f"CLEAR TO FLY | ALSFELD | {labels[day]} | P{page + 1} | {now}"
    if draw.textlength(footer, font=font_footer) > WIDTH - 10:
        footer = f"ALSFELD | {labels[day]} | SEITE {page + 1} | {now}"
    draw.text((5, footer_y + 4), footer, fill=0, font=font_footer)

    output = PUBLIC / f"day-{day}-page-{page}.png"
    canvas.save(output, format="PNG", optimize=True)
    print(f"Erstellt: {output} ({WIDTH}x{TOTAL_IMAGE_HEIGHT}) mit vier Bereichen: " + ", ".join(label for _, label in PAGE_SECTIONS[page]))
    return output


for day in range(3):
    for page in range(2):
        compose_page(day, page)

# Keep current.png for compatibility with the existing workflow's check.
shutil.copyfile(PUBLIC / "day-0-page-0.png", PUBLIC / "current.png")

cache_key = now_dt.strftime("%Y%m%d%H%M")
html = f'''<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ClearToFly Alsfeld – Kindle</title>
  <style type="text/css">
    html, body {{ margin: 0; padding: 0; width: 100%; background: #fff; color: #000; font-family: Arial, sans-serif; }}
    body {{ width: 100%; max-width: 600px; margin: 0 auto; overflow: hidden; }}
    #tabs {{ width: 100%; height: 40px; border-bottom: 1px solid #000; overflow: hidden; white-space: nowrap; }}
    .tab {{ float: left; display: block; width: 25%; height: 39px; line-height: 39px; text-align: center; box-sizing: border-box; border-right: 1px solid #777; color: #000; background: #fff; font-size: 12px; text-decoration: none; white-space: nowrap; overflow: hidden; }}
    .tab:last-child {{ border-right: 0; }}
    .tab.active {{ font-weight: bold; border-bottom: 4px solid #000; }}
    #weather {{ display: block; width: 100%; max-width: 600px; height: auto; border: 0; margin: 0; padding: 0; }}
  </style>
</head>
<body>
  <div id="tabs">
    <a class="tab active" id="tab0" href="#" onclick="showDay(0); return false;">HEUTE</a>
    <a class="tab" id="tab1" href="#" onclick="showDay(1); return false;">MORGEN</a>
    <a class="tab" id="tab2" href="#" onclick="showDay(2); return false;">ÜBERMORGEN</a>
    <a class="tab" id="pageButton" href="#" onclick="togglePage(); return false;">SEITE 1 &gt; 2</a>
  </div>
  <img id="weather" src="day-0-page-0.png?build={cache_key}" width="600" height="{TOTAL_IMAGE_HEIGHT}" alt="ClearToFly Flugwetter Alsfeld">
  <script type="text/javascript">
    var selectedDay = 0;
    var selectedPage = 0;
    function refreshImage() {{
      var image = document.getElementById('weather');
      if (image) image.src = 'day-' + selectedDay + '-page-' + selectedPage + '.png?refresh=' + new Date().getTime();
    }}
    function updateControls() {{
      for (var i = 0; i < 3; i++) {{
        var tab = document.getElementById('tab' + i);
        if (tab) tab.className = (i === selectedDay) ? 'tab active' : 'tab';
      }}
      var pageButton = document.getElementById('pageButton');
      if (pageButton) {{
        pageButton.innerHTML = selectedPage === 0 ? 'SEITE 1 &gt; 2' : 'SEITE 2 &gt; 1';
        pageButton.className = 'tab';
      }}
    }}
    function showDay(day) {{
      if (day < 0 || day > 2) return;
      selectedDay = day;
      updateControls();
      refreshImage();
    }}
    function togglePage() {{
      selectedPage = selectedPage === 0 ? 1 : 0;
      updateControls();
      refreshImage();
    }}
    updateControls();
    if (window.setInterval) window.setInterval(refreshImage, 900000);
  </script>
</body>
</html>
'''
(PUBLIC / "index.html").write_text(html, encoding="utf-8")
print("Erstellt: public/index.html")
print("6 Bilder für 3 Tage x 2 Seiten erstellt; vier Diagrammbereiche pro Seite.")
