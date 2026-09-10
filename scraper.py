#!/usr/bin/env python3
"""
Career Growth - daily news collector.

Reads sources.json, fetches each source, and writes data/news.json.

Strategy per source, in order:
  1. Use the explicit "rss" URL if one is configured.
  2. Try to auto-discover a feed (common paths + <link rel="alternate">).
  3. Fall back to pulling article links out of the HTML.

Every source is isolated in its own try/except, so one dead site never
stops the run. Failures are recorded in data/news.json under "sources"
so the website can show you exactly what worked this morning.

Run locally to test:      python scraper.py
Test one source only:     python scraper.py --only ican
Verbose diagnostics:      python scraper.py --only ican --verbose
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------- constants

ROOT = os.path.dirname(os.path.abspath(__file__))
SOURCES_FILE = os.path.join(ROOT, "sources.json")
DATA_DIR = os.path.join(ROOT, "data")
NEWS_FILE = os.path.join(DATA_DIR, "news.json")

NPT = timezone(timedelta(hours=5, minutes=45))   # Nepal Standard Time

ARCHIVE_DAYS = 45            # how long to keep old items
MAX_PER_SOURCE = 12          # items kept per source per run
REQUEST_TIMEOUT = 25
RETRIES = 2

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ne;q=0.8",
}

FEED_PATHS = [
    "/feed/", "/feed", "/rss/", "/rss", "/rss.xml", "/feed.xml",
    "/atom.xml", "/index.xml", "/feeds/posts/default", "/?feed=rss2",
]

# Link text that is navigation, not news.
NAV_WORDS = {
    "home", "about", "about us", "contact", "contact us", "login", "log in",
    "register", "sign up", "search", "more", "read more", "next", "previous",
    "privacy policy", "terms", "sitemap", "downloads", "download", "gallery",
    "photo gallery", "video", "videos", "advertise", "subscribe", "faq",
    "notice", "notices", "news", "all news", "archive", "english", "nepali",
    "back", "view all", "see all", "menu", "share", "facebook", "twitter",
    "मुख्य पृष्ठ", "गृहपृष्ठ", "हाम्रो बारे", "सम्पर्क", "थप", "पुरा पढ्नुहोस्",
    "सबै", "समाचार", "सूचना", "विज्ञापन",
}

# URL fragments that are never article pages.
BAD_URL_PARTS = (
    "/tag/", "/tags/", "/author/", "/category/page", "/wp-login",
    "/wp-admin", "javascript:", "mailto:", "tel:", "#", "/feed",
    "/login", "/register", "/search", ".jpg", ".png", ".gif", ".css", ".js",
)

DOC_EXTENSIONS = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip")

# Words that make an item matter more to a CA. Used for the "Key" flag.
PRIORITY_TERMS = [
    "circular", "directive", "notification", "notice", "amendment", "amend",
    "act", "regulation", "rule", "bylaw", "guideline", "standard", "nfrs",
    "ifrs", "nas", "audit", "auditor", "tax", "vat", "tds", "excise",
    "income tax", "finance act", "budget", "deadline", "due date", "penalty",
    "compliance", "filing", "return", "licence", "license", "monetary policy",
    "capital adequacy", "provision", "merger", "acquisition", "ipo", "fpo",
    "rights share", "dividend", "agm", "insolvency", "liquidation",
    "परिपत्र", "निर्देशन", "सूचना", "संशोधन", "ऐन", "नियमावली", "कर", "मूल्य अभिवृद्धि कर",
    "लेखापरीक्षण", "बजेट", "अन्तिम म्याद", "जरिवाना", "लाभांश", "निर्देशिका",
]


# ---------------------------------------------------------------- utilities

def log(msg, verbose_only=False, verbose=False):
    if verbose_only and not verbose:
        return
    print(msg, flush=True)


def now_npt():
    return datetime.now(NPT)


def clean_text(s):
    if not s:
        return ""
    s = BeautifulSoup(s, "html.parser").get_text(" ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def item_id(url, title):
    return hashlib.sha1(f"{url}|{title}".encode("utf-8", "ignore")).hexdigest()[:16]


def is_priority(title, summary=""):
    blob = f"{title} {summary}".lower()
    return any(term in blob for term in PRIORITY_TERMS)


def fetch(url, verbose=False, quick=False):
    """
    GET a URL with retries. Returns response or None.

    quick=True is used for feed-discovery probes: one attempt, short timeout.
    Without it, probing ten candidate feed paths on a dead site would stall
    the whole morning run.
    """
    attempts = 1 if quick else RETRIES + 1
    timeout = 6 if quick else REQUEST_TIMEOUT
    last_err = None
    for attempt in range(attempts):
        try:
            r = requests.get(
                url, headers=HEADERS, timeout=timeout, allow_redirects=True
            )
            if r.status_code == 200:
                return r
            last_err = f"HTTP {r.status_code}"
        except requests.exceptions.SSLError:
            # Several Nepali government sites have certificate issues.
            try:
                r = requests.get(
                    url, headers=HEADERS, timeout=timeout, verify=False
                )
                if r.status_code == 200:
                    log(f"      (connected without certificate check)", True, verbose)
                    return r
                last_err = f"HTTP {r.status_code}"
            except Exception as e:
                last_err = f"SSL + {type(e).__name__}"
        except Exception as e:
            last_err = f"{type(e).__name__}"
        if attempt < attempts - 1:
            time.sleep(1.5 * (attempt + 1))
    log(f"      fetch failed: {last_err}", True, verbose)
    return None


def parse_date(entry):
    """Pull a published date out of a feed entry. Returns ISO string or None."""
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        val = entry.get(key)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc).isoformat()
            except Exception:
                pass
    return None


# ------------------------------------------------------------ feed handling

def items_from_feed(feed_url, source, verbose=False):
    """Parse an RSS/Atom feed into item dicts. Returns [] if not a real feed."""
    resp = fetch(feed_url, verbose)
    if resp is None:
        return []

    parsed = feedparser.parse(resp.content)
    if not parsed.entries:
        return []

    items = []
    for entry in parsed.entries[:MAX_PER_SOURCE]:
        title = clean_text(entry.get("title", ""))
        link = entry.get("link", "")
        if not title or not link:
            continue
        summary = clean_text(entry.get("summary", ""))[:400]
        items.append({
            "id": item_id(link, title),
            "title": title,
            "url": link,
            "summary": summary,
            "published": parse_date(entry),
            "source": source["id"],
            "source_name": source["name"],
            "category": source["category"],
            "is_document": link.lower().endswith(DOC_EXTENSIONS),
            "priority": is_priority(title, summary),
        })
    if items:
        log(f"      feed gave {len(items)} items", True, verbose)
    return items


def discover_feed(page_url, verbose=False):
    """Look for a feed: declared in <head>, or at a common path."""
    resp = fetch(page_url, verbose)
    if resp is not None:
        try:
            soup = BeautifulSoup(resp.content, "html.parser")
            for link in soup.find_all("link", rel=lambda v: v and "alternate" in v):
                ctype = (link.get("type") or "").lower()
                if "rss" in ctype or "atom" in ctype or "xml" in ctype:
                    href = link.get("href")
                    if href:
                        found = urljoin(page_url, href)
                        log(f"      declared feed: {found}", True, verbose)
                        return found
        except Exception:
            pass

    base = f"{urlparse(page_url).scheme}://{urlparse(page_url).netloc}"
    for path in FEED_PATHS:
        candidate = base + path
        r = fetch(candidate, verbose=False, quick=True)
        if r is None:
            continue
        head = r.content[:600].lower()
        if b"<rss" in head or b"<feed" in head or b"<rdf" in head:
            log(f"      found feed at {candidate}", True, verbose)
            return candidate
    return None


# ------------------------------------------------------------ HTML fallback

def items_from_html(source, verbose=False):
    """
    Last resort: pull plausible article links off the page.

    Heuristic - a news link usually has text of a sentence-like length,
    lives inside a heading or article element, and points somewhere deeper
    than the homepage.
    """
    url = source["url"]
    resp = fetch(url, verbose)
    if resp is None:
        return []

    try:
        soup = BeautifulSoup(resp.content, "html.parser")
    except Exception:
        return []

    for junk in soup(["script", "style", "nav", "footer", "header", "aside"]):
        junk.decompose()

    scope = soup
    if source.get("selector"):
        picked = soup.select_one(source["selector"])
        if picked:
            scope = picked
        else:
            log(f"      selector '{source['selector']}' matched nothing", True, verbose)

    # Prefer links that sit inside headings or article containers.
    ranked = []
    for tag in scope.select("h1 a, h2 a, h3 a, h4 a, article a, .title a, .news-title a"):
        ranked.append((2, tag))
    for tag in scope.find_all("a"):
        ranked.append((1, tag))

    seen_urls = set()
    items = []
    base_domain = urlparse(url).netloc

    for weight, tag in sorted(ranked, key=lambda x: -x[0]):
        if len(items) >= MAX_PER_SOURCE:
            break

        href = tag.get("href", "")
        title = clean_text(tag.get_text())

        if not href or not title:
            continue
        if title.lower() in NAV_WORDS or title in NAV_WORDS:
            continue
        if any(bad in href.lower() for bad in BAD_URL_PARTS):
            continue

        # Sentence-like length. Too short is navigation, too long is a blurb.
        if not (18 <= len(title) <= 220):
            continue
        # A title that is only digits or punctuation is a date stamp.
        if not re.search(r"[A-Za-z\u0900-\u097F]{4,}", title):
            continue

        full = urljoin(url, href)
        if urlparse(full).netloc != base_domain:
            continue
        # Must be deeper than the site root.
        if len(urlparse(full).path.strip("/")) < 4:
            continue
        if full in seen_urls:
            continue
        seen_urls.add(full)

        items.append({
            "id": item_id(full, title),
            "title": title,
            "url": full,
            "summary": "",
            "published": None,
            "source": source["id"],
            "source_name": source["name"],
            "category": source["category"],
            "is_document": full.lower().endswith(DOC_EXTENSIONS),
            "priority": is_priority(title),
        })

    log(f"      html scrape gave {len(items)} items", True, verbose)
    return items


# ------------------------------------------------------------------ per src

def collect(source, verbose=False):
    """Returns (items, status_dict) for one source."""
    started = time.time()
    name = source["name"]
    log(f"  -> {name}")

    method = None
    items = []

    try:
        if source.get("rss"):
            items = items_from_feed(source["rss"], source, verbose)
            if items:
                method = "configured feed"

        if not items:
            found = discover_feed(source["url"], verbose)
            if found:
                items = items_from_feed(found, source, verbose)
                if items:
                    method = "discovered feed"
                    source["_discovered_rss"] = found

        if not items:
            items = items_from_html(source, verbose)
            if items:
                method = "page scrape"

        elapsed = round(time.time() - started, 1)

        if items:
            log(f"     {len(items)} items via {method}  ({elapsed}s)")
            return items, {
                "id": source["id"], "name": name, "ok": True,
                "count": len(items), "method": method, "seconds": elapsed,
                "error": None,
                "discovered_rss": source.get("_discovered_rss"),
            }

        log(f"     nothing found  ({elapsed}s)")
        return [], {
            "id": source["id"], "name": name, "ok": False, "count": 0,
            "method": None, "seconds": elapsed,
            "error": "No items found. Site may block automated access, "
                     "load content with JavaScript, or need a CSS selector "
                     "set in sources.json.",
            "discovered_rss": None,
        }

    except Exception as e:
        elapsed = round(time.time() - started, 1)
        log(f"     error: {type(e).__name__}: {e}")
        return [], {
            "id": source["id"], "name": name, "ok": False, "count": 0,
            "method": None, "seconds": elapsed,
            "error": f"{type(e).__name__}: {e}", "discovered_rss": None,
        }


# -------------------------------------------------------------------- merge

def merge_with_archive(fresh_items, today_str):
    """Keep history. Tag anything seen for the first time today as new."""
    existing = {}
    if os.path.exists(NEWS_FILE):
        try:
            with open(NEWS_FILE, encoding="utf-8") as f:
                old = json.load(f)
            for it in old.get("items", []):
                existing[it["id"]] = it
        except Exception as e:
            log(f"  (could not read previous news.json: {e})")

    merged = dict(existing)
    new_count = 0

    for it in fresh_items:
        if it["id"] in merged:
            # Already known - keep its original first_seen.
            prior = merged[it["id"]]
            it["first_seen"] = prior.get("first_seen", today_str)
            it["is_new"] = it["first_seen"] == today_str
        else:
            it["first_seen"] = today_str
            it["is_new"] = True
            new_count += 1
        merged[it["id"]] = it

    # Re-flag older items so yesterday's "new" badge clears.
    for it in merged.values():
        it["is_new"] = it.get("first_seen") == today_str

    cutoff = (now_npt() - timedelta(days=ARCHIVE_DAYS)).strftime("%Y-%m-%d")
    kept = [it for it in merged.values() if it.get("first_seen", today_str) >= cutoff]

    kept.sort(
        key=lambda it: (it.get("first_seen", ""), it.get("published") or ""),
        reverse=True,
    )
    return kept, new_count


# --------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="run a single source by id")
    ap.add_argument("--category", help="run one category only")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    with open(SOURCES_FILE, encoding="utf-8") as f:
        config = json.load(f)

    sources = config["sources"]
    if args.only:
        sources = [s for s in sources if s["id"] == args.only]
        if not sources:
            print(f"No source with id '{args.only}'.")
            return 1
    if args.category:
        sources = [s for s in sources if s["category"] == args.category]

    run_time = now_npt()
    today_str = run_time.strftime("%Y-%m-%d")

    print(f"\nCareer Growth collector")
    print(f"Run at {run_time.strftime('%Y-%m-%d %H:%M')} Nepal time")
    print(f"{len(sources)} sources\n")

    all_items = []
    statuses = []

    for source in sources:
        items, status = collect(source, args.verbose)
        all_items.extend(items)
        statuses.append(status)

    items, new_count = merge_with_archive(all_items, today_str)

    working = sum(1 for s in statuses if s["ok"])
    payload = {
        "generated_at": run_time.isoformat(),
        "generated_date": today_str,
        "new_today": new_count,
        "total_items": len(items),
        "sources_working": working,
        "sources_total": len(statuses),
        "sources": statuses,
        "items": items,
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(NEWS_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    print(f"\n{'-' * 52}")
    print(f"  {working} of {len(statuses)} sources responded")
    print(f"  {new_count} new items, {len(items)} in archive")
    print(f"  written to {NEWS_FILE}")

    broken = [s for s in statuses if not s["ok"]]
    if broken:
        print(f"\n  Not working:")
        for s in broken:
            print(f"    - {s['name']}: {s['error'][:70]}")

    discovered = [s for s in statuses if s.get("discovered_rss")]
    if discovered:
        print(f"\n  Feeds found (paste into sources.json to speed up future runs):")
        for s in discovered:
            print(f"    {s['id']}: {s['discovered_rss']}")
    print()

    return 0


if __name__ == "__main__":
    try:
        import urllib3
        urllib3.disable_warnings()
    except Exception:
        pass
    sys.exit(main())
