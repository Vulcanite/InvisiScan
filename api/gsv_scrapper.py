import uuid

from PIL import Image
from playwright.sync_api import sync_playwright, TimeoutError
import os
from time import perf_counter
import random, csv

NUM_IMAGES = 32000
IMAGE_WIDTH = 1920
IMAGE_HEIGHT = 1080

GSV_SCRAPER_OUT = 'gsv_scraper_out'
IMAGES_CSV = os.path.join(GSV_SCRAPER_OUT, 'images.csv')
IMAGES_DIR = os.path.join(GSV_SCRAPER_OUT, 'images')

INPUT_COORDS_CSV = "csv file to your coordinates."
start_time = perf_counter()


def load_points_from_csv(path):
    """
    Read (lat, lng) pairs from a CSV with flexible headers.
    Accepts any of: lat|latitude, lng|lon|long|longitude (case-insensitive).
    Skips rows with missing/invalid coords.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Input file not found: {path}")

    with open(path, 'r', newline='') as f:
        reader = csv.DictReader(f)
        # find columns (case-insensitive)
        cols = {k.lower(): k for k in reader.fieldnames or []}
        print(cols)
        lat_key = 'lat'
        lng_key = 'lon'
        if not lat_key or not lng_key:
            raise ValueError(
                "Could not find latitude/longitude columns. "
                "Expected headers like 'lat'/'latitude' and 'lng'/'lon'/'longitude'."
            )
        pts = []
        for row in reader:
            try:
                lat = float(row[lat_key])
                lng = float(row[lng_key])
                # basic sanity bounds
                if -90 <= lat <= 90 and -180 <= lng <= 180:
                    pts.append((lat, lng))
            except (TypeError, ValueError):
                continue
    return pts

def is_black_image(path, threshold=10):
    """Return True if screenshot is (mostly) black."""
    with Image.open(path) as im:
        im = im.convert("L")  # grayscale
        extrema = im.getextrema()  # (min, max)
        return extrema[1] <= threshold

# --- Main --------------------------------------------------------------------

def main():
    # Ensure output dirs & CSV exist with header
    if not os.path.isdir(GSV_SCRAPER_OUT):
        os.makedirs(GSV_SCRAPER_OUT)
    if not os.path.isdir(IMAGES_DIR):
        os.makedirs(IMAGES_DIR)
    if not os.path.isfile(IMAGES_CSV):
        with open(IMAGES_CSV, 'w', newline='') as images_csv:
            writer = csv.writer(images_csv)
            writer.writerow(['uid', 'lat', 'lng', 'url'])

    # Load coordinate list from the provided file
    coords = load_points_from_csv(INPUT_COORDS_CSV)
    if not coords:
        print("No valid coordinates found in the input file. Exiting.")
        return

    max_count = min(NUM_IMAGES, len(coords))
    print(f"Preparing to scrape up to {max_count} Street View frames from {INPUT_COORDS_CSV}.")

    # Do the scraping
    with sync_playwright() as playwright, playwright.webkit.launch() as browser:
        context = browser.new_context(viewport={'width': IMAGE_WIDTH, 'height': IMAGE_HEIGHT})
        page = context.new_page()

        # Iterate through coord rows, skipping any that already have a pano_id
        idx = 0
        scraped = 0
        while scraped < max_count and idx < len(coords):
            try:
                lat, lng = coords[idx]
                idx += 1  # move to next row for the next loop iteration

                heading = random.uniform(0, 360)  # still randomize heading per point

                url = f'https://www.google.com/maps/@{lat},{lng},3a,75y,{heading}h,90t/data=!3m6!1e1!3m4!1s!2e0!7i16384!8i8192'
                print(url)
                page.goto(url)

                page.wait_for_selector('canvas', timeout=5000)  # wait for canvas to load
                js_injection = """
                  canvas = document.querySelector('canvas');
                  if (canvas) {
                    let context = canvas.getContext('webgl') || canvas.getContext('webgl2');
                    if (context) {
                      context.drawArrays = function() { }
                    }
                  }
                """
                page.evaluate_handle(js_injection)

                # Wait for imagery to resolve (selector may need adjustment over time)
                page.wait_for_selector('#minimap div div:nth-child(2)', timeout=5000)

                elements_to_hide = """
                  .app-viewcard-strip,
                  .scene-footer,
                  #titlecard,
                  #watermark,
                  #image-header {
                    display: none;
                  }
                """
                page.add_style_tag(content=elements_to_hide)

                uid = str(uuid.uuid4())
                out_name = f'{uid}.png'
                out_path = os.path.join(IMAGES_DIR, out_name)
                page.screenshot(path=out_path)

                if is_black_image(out_path):
                    print("⚠️ Black image — skipping")
                    os.remove(out_path)
                    continue

                with open(IMAGES_CSV, 'a', newline='') as images_csv:
                    writer = csv.writer(images_csv)
                    writer.writerow([uid, lat, lng, url])

                scraped += 1
                print(f'scraped: {scraped}/{max_count}, time: {round(perf_counter() - start_time, 1)}s')

            except TimeoutError:
                continue

    print('done!\n')

if __name__ == '__main__':
    main()
