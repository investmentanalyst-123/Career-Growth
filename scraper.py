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

import plan
import securities
from bs4 import BeautifulSoup

# ---------------------------------------------------------------- constants

ROOT = os.path.dirname(os.path.abspath(__file__))
SOURCES_FILE = os.path.join(ROOT, "sources.json")
DATA_DIR = os.path.join(ROOT, "data")
NEWS_FILE = os.path.join(DATA_DIR, "news.json")

NPT = timezone(timedelta(hours=5, minutes=45))   # Nepal Standard Time

ARCHIVE_DAYS = 15            # how long to keep old items before they drop off
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

# For general news sites (Ratopati, Setopati, Online Khabar) whose feeds carry
# the whole paper. An item is kept only if it mentions something economic.
# This is what stops crime and weather stories reaching your morning briefing.
FINANCE_TERMS = [
    "bank", "banking", "tax", "vat", "revenue", "budget", "economy", "economic",
    "finance", "financial", "fiscal", "monetary", "nepse", "share", "stock",
    "ipo", "fpo", "dividend", "investment", "investor", "loan", "credit",
    "interest rate", "inflation", "insurance", "audit", "accounting", "company",
    "business", "trade", "export", "import", "remittance", "gdp", "capital",
    "merger", "profit", "loss", "turnover", "microfinance", "cooperative",
    "nrb", "sebon", "ican", "ird", "customs", "excise", "tariff", "subsidy",
    # Devanagari. Short words like "कर" (tax) are deliberately excluded -
    # they appear inside unrelated words such as "स्पष्टीकरण" and would let
    # general news through. Longer, unambiguous forms are used instead.
    "बैंक", "बैंकिङ", "आयकर", "करदाता", "कर छुट", "करको", "मूल्य अभिवृद्धि",
    "राजस्व", "बजेट", "अर्थतन्त्र", "आर्थिक", "वित्त", "वित्तीय", "नेप्से",
    "सेयर", "शेयर", "आइपीओ", "एफपीओ", "लाभांश", "लगानी", "ऋण", "ब्याजदर",
    "मुद्रास्फीति", "बीमा", "लेखापरीक्षण", "कम्पनी", "व्यापार", "निर्यात",
    "आयात", "रेमिट्यान्स", "पुँजी", "नाफा", "लघुवित्त", "सहकारी", "भन्सार",
    "उद्योग", "बजार", "मुद्रा", "राष्ट्र बैंक", "धितोपत्र", "बोर्ड",
    "अर्थमन्त्री", "अर्थ मन्त्रालय", "व्यवसाय", "कारोबार", "मर्जर",
]


def is_finance(title, summary=""):
    blob = f"{title} {summary}".lower()
    return any(term in blob for term in FINANCE_TERMS)


# Words that make an item matter more to a CA. Used for the "Key" flag.
PRIORITY_TERMS = [
    "circular", "directive", "notification", "notice", "amendment", "amend",
    "act", "regulation", "rule", "bylaw", "guideline", "standard", "nfrs",
    "ifrs", "nas", "audit", "auditor", "tax", "vat", "tds", "excise",
    "income tax", "finance act", "budget", "deadline", "due date", "penalty",
    "compliance", "filing", "return", "licence", "license", "monetary policy",
    "capital adequacy", "provision", "merger", "acquisition", "ipo", "fpo",
    "rights share", "dividend", "agm", "insolvency", "liquidation",
    "परिपत्र", "निर्देशन", "सूचना", "संशोधन", "नियमावली", "आयकर", "करदाता",
    "मूल्य अभिवृद्धि कर", "लेखापरीक्षण", "बजेट", "अन्तिम म्याद", "जरिवाना",
    "लाभांश", "निर्देशिका", "धितोपत्र", "प्रतिवेदन",
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


def registrable(host):
    """Reduce a hostname to its site-identifying part: www.ird.gov.np -> ird.gov.np"""
    host = (host or "").lower().lstrip(".")
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    # Handle two-level public suffixes such as .gov.np, .com.np, .co.uk
    if len(parts) >= 3 and parts[-2] in {"gov", "com", "org", "net", "edu", "co", "ac"}:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def same_site(url_a, url_b):
    return registrable(urlparse(url_a).netloc) == registrable(urlparse(url_b).netloc)


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

    # Attribution guard.
    #
    # Several Nepali government sites share one CMS, and a shared /rss/ or
    # /feed/ path can serve content that does not belong to the site being
    # read. An item labelled "Inland Revenue Dept" that opens someone else's
    # article is worse than a missing item, so links that point off the
    # source's own domain are rejected. Aggregators that link outward by
    # design set "allow_offsite": true in sources.json.
    allow_offsite = bool(source.get("allow_offsite"))
    offsite = 0

    items = []
    for entry in parsed.entries[:MAX_PER_SOURCE]:
        title = clean_text(entry.get("title", ""))
        link = entry.get("link", "")
        if not title or not link:
            continue

        if not allow_offsite and not same_site(link, source["url"]):
            offsite += 1
            log(f"      dropped offsite link: {urlparse(link).netloc}", True, verbose)
            continue

        summary = clean_text(entry.get("summary", ""))[:400]
        if source.get("filter") == "finance" and not is_finance(title, summary):
            continue
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
    # If most of the feed pointed elsewhere, this feed does not belong to this
    # source. Return nothing so the collector falls back to reading the page.
    total_seen = len(items) + offsite
    if offsite and total_seen and offsite > total_seen / 2:
        log(f"     feed rejected: {offsite}/{total_seen} links belonged to "
            f"another site, falling back to page scrape")
        return []

    if offsite:
        log(f"      {offsite} offsite item(s) dropped", True, verbose)
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
        # Government notice pages often use very terse titles, so sources
        # marked "relaxed" get a lower floor.
        floor = 10 if source.get("relaxed") else 18
        if not (floor <= len(title) <= 240):
            continue
        # A title that is only digits or punctuation is a date stamp.
        if not re.search(r"[A-Za-z\u0900-\u097F]{4,}", title):
            continue

        full = urljoin(url, href)
        if not same_site(full, url):
            continue
        # Must be deeper than the site root, unless relaxed.
        min_depth = 1 if source.get("relaxed") else 4
        if len(urlparse(full).path.strip("/")) < min_depth:
            continue
        if full in seen_urls:
            continue
        if source.get("filter") == "finance" and not is_finance(title):
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

def merge_with_archive(fresh_items, today_str, source_urls=None):
    """
    Keep history. Tag anything seen for the first time today as new.

    The archive is also cleaned on every run. Items collected before the
    attribution guard existed can still be sitting in history pointing at
    another site, and an item labelled "Inland Revenue Dept" that opens
    somebody else's article is worse than no item at all. Anything whose
    link does not belong to its own source is dropped here, so bad history
    is repaired rather than waiting fifteen days to expire.
    """
    source_urls = source_urls or {}
    existing = {}
    dropped_bad = 0
    dropped_seed = 0

    if os.path.exists(NEWS_FILE):
        try:
            with open(NEWS_FILE, encoding="utf-8") as f:
                old = json.load(f)
            for it in old.get("items", []):
                # Placeholder rows from the very first install.
                if str(it.get("title", "")).startswith("Sample \u2014") or it.get("url") == "#":
                    dropped_seed += 1
                    continue

                home = source_urls.get(it.get("source"))
                allow = source_urls.get("__offsite__", set())
                if (home and it.get("url")
                        and it.get("source") not in allow
                        and not same_site(it["url"], home)):
                    dropped_bad += 1
                    continue

                existing[it["id"]] = it
        except Exception as e:
            log(f"  (could not read previous news.json: {e})")

    if dropped_seed:
        log(f"  removed {dropped_seed} placeholder item(s) from the archive")
    if dropped_bad:
        log(f"  removed {dropped_bad} archived item(s) whose link belonged to "
            f"another site")

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

    # One notice often appears under several URLs on the same site, which
    # would otherwise list it four or five times. Keep the earliest copy.
    def title_key(it):
        t = re.sub(r"[^\w\u0900-\u097F]+", "", (it.get("title") or "").lower())
        return (it.get("source"), t[:90])

    kept.sort(key=lambda it: it.get("first_seen", ""))
    seen_titles, deduped = set(), []
    for it in kept:
        k = title_key(it)
        if k[1] and k in seen_titles:
            continue
        seen_titles.add(k)
        deduped.append(it)
    if len(deduped) != len(kept):
        log(f"  merged {len(kept) - len(deduped)} duplicate item(s) "
            f"published under more than one link")
    kept = deduped

    kept.sort(
        key=lambda it: (it.get("first_seen", ""), it.get("published") or ""),
        reverse=True,
    )

    # Two runs a day means the afternoon run must not report only its own
    # additions - "new today" covers everything first seen today, morning
    # items included.
    new_today = sum(1 for it in kept if it.get("first_seen") == today_str)
    dropped = len(merged) - len(kept)
    if dropped:
        log(f"  {dropped} item(s) older than {ARCHIVE_DAYS} days removed")
    return kept, new_today, new_count


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

    skipped = [s for s in sources if s.get("enabled") is False]
    sources = [s for s in sources if s.get("enabled") is not False]
    if skipped and not args.only:
        print(f"Skipping {len(skipped)} disabled source(s): "
              + ", ".join(s["name"] for s in skipped))

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

    source_urls = {s["id"]: s["url"] for s in config["sources"]}
    source_urls["__offsite__"] = {s["id"] for s in config["sources"]
                                  if s.get("allow_offsite")}
    items, new_today, added_now = merge_with_archive(all_items, today_str, source_urls)

    # Build the government securities calendar from PDMO auction notices.
    sec_ids = {s["id"] for s in config["sources"] if s.get("securities")}
    sec_items = [i for i in items if i.get("source") in sec_ids]
    try:
        secs = securities.extract(sec_items)
        print(f"\n  {len(secs)} government security auction(s) parsed from "
              f"{len(sec_items)} PDMO notice(s)")
        for e in secs[:5]:
            print(f"    {e['type']:<18} {e['bs_date']}  {e['tenor'] or '-'}")
    except Exception as e:
        print(f"  securities parsing failed: {e}")
        secs = []

    # Read the published annual issuance plan. This gives forward visibility
    # months ahead of the individual auction notices, and picks up next
    # year's plan automatically when PDMO publishes it around Shrawan.
    planned, plan_title = plan.collect(fetch)

    # Match announced auctions to their planned row. A notice states the
    # auction date; the plan states both the auction and the issue date. So
    # the plan row is kept (it carries the issue date and the amount) and is
    # marked as announced, with the notice's link and ISIN attached.
    by_auction = {}
    for e in secs:
        by_auction.setdefault((e["type"], e.get("auction_date")), e)

    matched = set()
    for row in planned:
        key = (row["type"], row.get("auction_date"))
        hit = by_auction.get(key)
        if hit:
            row["confirmed"] = True
            row["url"] = hit.get("url") or row.get("url")
            row["isin"] = hit.get("isin") or row.get("isin")
            row["title"] = hit.get("title", "")
            matched.add(id(hit))

    # Anything announced that is not in the plan still belongs in the tracker.
    extras = [e for e in secs if id(e) not in matched]
    for e in extras:
        e["confirmed"] = True
        e["planned"] = False

    combined = planned + extras
    print(f"  matched {len(matched)} announced auction(s) to the published plan")
    combined.sort(key=lambda x: x["issue_date"])
    n_conf = sum(1 for e in combined if e.get("confirmed"))
    print(f"  securities tracker: {len(combined)} entries "
          f"({n_conf} announced, {len(combined) - n_conf} scheduled)")

    working = sum(1 for s in statuses if s["ok"])
    payload = {
        "generated_at": run_time.isoformat(),
        "generated_date": today_str,
        "new_today": new_today,
        "added_this_run": added_now,
        "total_items": len(items),
        "sources_working": working,
        "sources_total": len(statuses),
        "sources": statuses,
        "securities": combined,
        "plan_title": plan_title,
        "items": items,
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(NEWS_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    print(f"\n{'-' * 52}")
    print(f"  {working} of {len(statuses)} sources responded")
    print(f"  {added_now} added this run, {new_today} new today, "
          f"{len(items)} in archive (last {ARCHIVE_DAYS} days)")
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
