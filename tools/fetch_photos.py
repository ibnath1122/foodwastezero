"""Download real, freely licensed photos for products that do not have one yet.

Run this on a machine WITH internet access (Wikimedia Commons is used; no API key needed):

    pip install Pillow
    python tools/fetch_photos.py            # fetch only products that have no photo yet
    python tools/fetch_photos.py --force    # re-download everything in the list
    python tools/fetch_photos.py PRO-001    # one SKU only

Photos are saved as static/img/products/<SKU>.jpg (800x600) and every download is logged with author + licence in
static/img/products/CREDITS.txt. Open the shop afterwards and replace any photo you don't like from
Products -> Edit -> Product photo (or drop your own <SKU>.jpg into the folder).
"""
import io
import json
import os
import sys
import time
import urllib.parse
import urllib.request

from PIL import Image, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "static", "img", "products")
API = "https://commons.wikimedia.org/w/api.php"
UA = "FoodWasteZero/1.0 (hackathon demo; photo fetch script)"
OK_LICENSES = ("cc0", "public domain", "pd", "cc by", "cc-by")          # CC BY / BY-SA need the credit line below
BAD_WORDS = ("diagram", "logo", "icon", "map", "chart", "drawing", "illustration", "svg", "vector", "label")

# SKU -> search phrases (first one that gives a usable landscape photo wins)
TERMS = {
    "BAK-001": ["sliced sandwich bread loaf", "white bread loaf"],
    "DAI-001": ["glass of milk and bottle", "pasteurized milk bottle"],
    "DAI-003": ["eggs carton dozen", "brown eggs"],
    "DAI-004": ["paneer cheese cubes", "indian paneer"],
    "PRO-001": ["bananas bunch", "ripe bananas"],
    "PRO-002": ["tomatoes fresh red", "tomato market"],
    "PRO-003": ["spinach bunch fresh", "palong shak"],
    "PRO-004": ["green chili peppers", "green chilies market bangladesh"],
    "MEA-001": ["raw chicken meat market", "broiler chicken meat"],
    "MEA-002": ["rohu fish market", "rui fish bangladesh"],
    "MEA-003": ["minced beef raw", "ground beef raw"],
    "BEV-001": ["orange juice glass", "fresh orange juice bottle"],
    "BEV-002": ["lassi glass", "sweet lassi"],
    "PKG-002": ["biscuits packet", "assorted biscuits"],
}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read()


def search(term):
    q = {"action": "query", "format": "json", "generator": "search", "gsrsearch": "filetype:bitmap " + term,
         "gsrnamespace": "6", "gsrlimit": "12", "prop": "imageinfo", "iiprop": "url|size|extmetadata", "iiurlwidth": "900"}
    data = json.loads(get(API + "?" + urllib.parse.urlencode(q)))
    pages = sorted((data.get("query", {}).get("pages", {})).values(), key=lambda p: p.get("index", 99))
    for p in pages:
        info = (p.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        lic = (meta.get("LicenseShortName", {}).get("value", "") or "").lower()
        title = p.get("title", "").lower()
        if not info.get("thumburl") or info.get("width", 0) < 700 or info.get("width", 0) < info.get("height", 1):
            continue
        if any(w in title for w in BAD_WORDS) or not any(lic.startswith(k) for k in OK_LICENSES):
            continue
        author = (meta.get("Artist", {}).get("value", "") or "unknown")
        author = "".join(ch for ch in author if ch not in "<>")[:80]
        yield {"title": p["title"], "url": info["thumburl"], "page": info.get("descriptionurl", ""),
               "license": meta.get("LicenseShortName", {}).get("value", ""), "author": author}


def main(argv):
    force = "--force" in argv
    wanted = [a for a in argv if not a.startswith("--")] or list(TERMS)
    os.makedirs(OUT, exist_ok=True)
    for sku in wanted:
        dest = os.path.join(OUT, sku + ".jpg")
        if os.path.exists(dest) and not force:
            print(sku, "already has a photo - skipped")
            continue
        done = False
        for term in TERMS.get(sku, []):
            try:
                for hit in search(term):
                    img = ImageOps.exif_transpose(Image.open(io.BytesIO(get(hit["url"])))).convert("RGB")
                    ImageOps.fit(img, (800, 600), method=Image.LANCZOS).save(dest, quality=82, optimize=True, progressive=True)
                    with open(os.path.join(OUT, "CREDITS.txt"), "a", encoding="utf-8") as f:
                        f.write("%s  %s | %s | %s | %s\n" % (sku, hit["title"], hit["author"], hit["license"], hit["page"]))
                    print(sku, "OK  ", hit["title"], "(%s)" % hit["license"])
                    done = True
                    break
            except Exception as e:          # network hiccup / odd image: try the next phrase
                print(sku, "retry:", e)
            if done:
                break
            time.sleep(1)
        if not done:
            print(sku, "no suitable photo found - upload one from Products -> Edit")
        time.sleep(1)


if __name__ == "__main__":
    main(sys.argv[1:])
