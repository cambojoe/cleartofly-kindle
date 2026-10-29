from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageEnhance
import shutil

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
PUBLIC.mkdir(parents=True, exist_ok=True)

WIDTH = 600
CONTENT_HEIGHT = 740
FOOTER_HEIGHT = 20
TOTAL_IMAGE_HEIGHT = CONTENT_HEIGHT + FOOTER_HEIGHT
RAW_TEMPLATE = "/tmp/cleartofly-day-{day}-page-{page}-raw.png"
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


def make_image(day, page):
    raw_path = Path(RAW_TEMPLATE.format(day=day, page=page))
    if not raw_path.exists():
        raise SystemExit(f"Screenshot fehlt: {raw_path}. ClearToFly hat die Diagramme vermutlich nicht erfasst.")

    with Image.open(raw_path) as source:
        if source.width != WIDTH:
            raise SystemExit(f"Unerwartete Bildbreite für Tag {day + 1}, Seite {page + 1}: {source.width}; erwartet {WIDTH}.")
        image = source.convert("L")
        if image.height > CONTENT_HEIGHT:
            # Preserve the complete chart stack (especially Visibility at the
            # bottom of page 2) instead of cropping off its lower edge.
            image = image.resize((WIDTH, CONTENT_HEIGHT), Image.Resampling.LANCZOS)
        image = ImageOps.autocontrast(image, cutoff=0.4)
        image = ImageEnhance.Contrast(image).enhance(1.10)

        # Do not stretch a shorter diagram stack vertically: retaining the
        # original proportions keeps chart text and wind barbs readable.
        canvas = Image.new("L", (WIDTH, TOTAL_IMAGE_HEIGHT), 255)
        canvas.paste(image, (0, 0))

    draw = ImageDraw.Draw(canvas)
    footer_y = CONTENT_HEIGHT
    draw.line((0, footer_y, WIDTH - 1, footer_y), fill=0, width=1)
    page_name = "SEITE 1: TEMP / WIND / QUERWIND" if page == 0 else "SEITE 2: WOLKEN / SICHT / PISTENWIND"
    footer = f"CLEAR TO FLY | ALSFELD | {labels[day]} | {page_name} | {now}"
    # Keep footer short enough for the 600-pixel Kindle display.
    if draw.textlength(footer, font=font_footer) > WIDTH - 10:
        page_name = "SEITE 1" if page == 0 else "SEITE 2"
        footer = f"CLEAR TO FLY | ALSFELD | {labels[day]} | {page_name} | {now}"
    draw.text((5, footer_y + 4), footer, fill=0, font=font_footer)

    output = PUBLIC / f"day-{day}-page-{page}.png"
    canvas.save(output, format="PNG", optimize=True)
    print(f"Erstellt: {output} ({WIDTH}x{TOTAL_IMAGE_HEIGHT})")
    return output


for day in range(3):
    for page in range(2):
        make_image(day, page)

# Keep current.png for compatibility with the existing workflow's check and
# to make the first default view the current-day first page.
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
    // Refresh only the image so that the selected day and page are not reset.
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
print(f"Erstellt: {PUBLIC / 'index.html'}")
print("6 Bilder für 3 Tage x 2 Seiten erstellt; vier auswählbare Schaltflächen bleiben für den Kindle kompatibel.")
