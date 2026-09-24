#!/usr/bin/env python3
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

PROFILE_URL = "https://funpay.com/users/624432/"
OUT = Path("reviews.json")
MAX_REVIEWS = 12


def fetch_html() -> str:
    # curl_cffi imitates a normal Chrome TLS/browser fingerprint and is usually
    # more reliable for public pages protected by basic anti-bot checks.
    try:
        from curl_cffi import requests as crequests
        r = crequests.get(
            PROFILE_URL,
            impersonate="chrome",
            timeout=30,
            headers={
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
                "Referer": "https://funpay.com/",
            },
        )
        r.raise_for_status()
        return r.text
    except Exception as first_error:
        import requests
        try:
            r = requests.get(
                PROFILE_URL,
                timeout=30,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/151.0.0.0 Safari/537.36"
                    ),
                    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
                    "Referer": "https://funpay.com/",
                },
            )
            r.raise_for_status()
            return r.text
        except Exception as second_error:
            raise RuntimeError(
                f"FunPay fetch failed. curl_cffi: {first_error}; requests: {second_error}"
            )


def clean(s: str | None) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", s).strip()


def parse_stars(node) -> int:
    if node is None:
        return 5

    # Common FontAwesome / rating markup patterns.
    for selector in (
        ".rating-stars .fas",
        ".rating-stars .fa-star",
        "i.fas.fa-star",
        "i.fa-star",
        "[class*='star'][class*='active']",
    ):
        found = node.select(selector)
        if 1 <= len(found) <= 5:
            return len(found)

    text = node.get_text(" ", strip=True)
    star_count = text.count("★")
    if 1 <= star_count <= 5:
        return star_count

    # FunPay seller reviews shown in this profile are normally 5-star rows;
    # use 5 only as display fallback if the markup does not expose star count.
    return 5


def deepest_review_nodes(soup: BeautifulSoup):
    """Find DOM blocks that look like one FunPay review row."""
    selectors = [
        ".review-container",
        ".review-item",
        ".reviews-list .media",
        ".reviews .media",
        "[class*='review']",
    ]
    candidates = []
    seen = set()
    for selector in selectors:
        for node in soup.select(selector):
            text = clean(node.get_text(" ", strip=True))
            if "Заказ #" not in text and "Order #" not in text:
                continue
            key = id(node)
            if key not in seen:
                candidates.append(node)
                seen.add(key)

    # Keep the smallest/deepest candidates so a parent list is not treated as one review.
    result = []
    for node in candidates:
        child_has_review = any(
            ("Заказ #" in clean(ch.get_text(" ", strip=True)) or "Order #" in clean(ch.get_text(" ", strip=True)))
            for ch in node.find_all(recursive=False)
        )
        if not child_has_review:
            result.append(node)
    return result


def parse_review_node(node) -> dict | None:
    raw = clean(node.get_text("\n", strip=True))
    m = re.search(r"(?:Заказ|Order)\s+#([A-Z0-9]+)", raw, re.I)
    if not m:
        return None
    order_id = m.group(1)

    # Author: prefer links/names before the order marker.
    author = "Покупатель"
    for selector in (".media-user-name", ".review-author", ".user-link-name", "strong", "b", "a"):
        el = node.select_one(selector)
        if el:
            val = clean(el.get_text(" ", strip=True))
            if val and "Заказ" not in val and "Order" not in val and len(val) <= 60:
                author = val
                break
    if author == "Покупатель":
        before = raw[: m.start()]
        tokens = [x.strip() for x in re.split(r"\n|\s{2,}", before) if x.strip()]
        if tokens:
            author = tokens[-1][:60]

    lines = [clean(x) for x in node.get_text("\n", strip=True).splitlines() if clean(x)]
    order_line_idx = next((i for i, x in enumerate(lines) if re.search(r"(?:Заказ|Order)\s+#" + re.escape(order_id), x, re.I)), -1)

    meta = lines[order_line_idx] if order_line_idx >= 0 else ""
    # Remove author/order prefix and leave date/relative date if present.
    meta = re.sub(r"^.*?(?:Заказ|Order)\s+#" + re.escape(order_id), "", meta, flags=re.I).strip(" ,—-")

    game = "World of Tanks"
    price = ""
    game_idx = -1
    for i, line in enumerate(lines):
        if "World of Tanks" in line:
            game_idx = i
            game = "World of Tanks"
            pm = re.search(r"(?:World of Tanks\s*,?\s*)([^,\n]+(?:\$|€|₽|руб\.?))", line, re.I)
            if pm:
                price = clean(pm.group(1))
            else:
                pm = re.search(r"([0-9][0-9\s.,]*\s*[$€₽])", line)
                if pm:
                    price = clean(pm.group(1))
            break

    # Review text usually follows the game/price line. Ignore UI/rating noise.
    text = ""
    if game_idx >= 0:
        for line in lines[game_idx + 1 :]:
            if not line or line.count("★") >= 3:
                continue
            if re.fullmatch(r"[★☆\s]+", line):
                continue
            if re.search(r"^(Все отзывы|All reviews)$", line, re.I):
                continue
            text = line
            break

    return {
        "author": author,
        "order_id": order_id,
        "date": meta,
        "game": game,
        "price": price,
        "stars": parse_stars(node),
        "text": text,
    }


def parse_reviews_from_text(soup: BeautifulSoup) -> list[dict]:
    """Fallback parser if FunPay changes CSS class names."""
    lines = [clean(x) for x in soup.get_text("\n", strip=True).splitlines() if clean(x)]
    out = []
    for i, line in enumerate(lines):
        m = re.search(r"^(.*?)\s+(?:Заказ|Order)\s+#([A-Z0-9]+)\s*(.*)$", line, re.I)
        if not m:
            continue
        author = clean(m.group(1)) or "Покупатель"
        order_id = m.group(2)
        meta = clean(m.group(3)).strip(" ,—-")
        game_line = lines[i + 1] if i + 1 < len(lines) else ""
        if "World of Tanks" not in game_line:
            continue
        pm = re.search(r"([0-9][0-9\s.,]*\s*[$€₽])", game_line)
        price = clean(pm.group(1)) if pm else ""
        review_text = ""
        for line2 in lines[i + 2 : i + 6]:
            if re.search(r"(?:Заказ|Order)\s+#", line2, re.I):
                break
            if line2.count("★") >= 3 or re.fullmatch(r"[★☆\s]+", line2):
                continue
            review_text = line2
            break
        out.append({
            "author": author[:60],
            "order_id": order_id,
            "date": meta,
            "game": "World of Tanks",
            "price": price,
            "stars": 5,
            "text": review_text,
        })
    return out


def dedupe(reviews: list[dict]) -> list[dict]:
    result = []
    seen = set()
    for r in reviews:
        key = r.get("order_id") or (r.get("author"), r.get("text"))
        if key in seen:
            continue
        seen.add(key)
        result.append(r)
    return result


def parse_profile(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    page_text = clean(soup.get_text(" ", strip=True))

    # Profile summary. Keep current value if FunPay wording differs.
    total_reviews = None
    for pattern in (
        r"([0-9][0-9\s]*)\s+отзыв(?:а|ов)?\b",
        r"([0-9][0-9\s]*)\s+reviews?\b",
    ):
        m = re.search(pattern, page_text, re.I)
        if m:
            total_reviews = int(m.group(1).replace(" ", ""))
            break

    rating = 5.0
    # Try profile rating block first.
    rating_node = soup.select_one(".rating-value, .rating-big, [class*='rating']")
    if rating_node:
        m = re.search(r"\b([1-5](?:[.,][0-9])?)\b", clean(rating_node.get_text(" ", strip=True)))
        if m:
            rating = float(m.group(1).replace(",", "."))

    reviews = []
    for node in deepest_review_nodes(soup):
        parsed = parse_review_node(node)
        if parsed:
            reviews.append(parsed)
    reviews = dedupe(reviews)

    if not reviews:
        reviews = dedupe(parse_reviews_from_text(soup))

    # Keep only World of Tanks reviews if enough are available, otherwise keep all parsed rows.
    wot = [r for r in reviews if r.get("game") == "World of Tanks"]
    if wot:
        reviews = wot

    if not reviews:
        raise RuntimeError("No reviews found in FunPay profile HTML. The page layout may have changed or access was blocked.")

    return {
        "source": PROFILE_URL,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rating": rating,
        "total_reviews": total_reviews,
        "reviews": reviews[:MAX_REVIEWS],
    }


def main():
    html = fetch_html()
    data = parse_profile(html)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(data['reviews'])} reviews to {OUT}")
    print(f"Total reviews: {data.get('total_reviews')}; rating: {data.get('rating')}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
