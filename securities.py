"""
Government securities calendar.

PDMO announces every auction with a highly structured title, for example:

  मिति २०८३ भाद्र २४ गते बोलकबोल मार्फत विकास ऋणपत्र-२०८८ (NPDB05122088)(५ वर्षे)
  मिति २०८३।०५।०१ गते हुने TBills को बोलकबोलको सूचना
  ९१ दिने ट्रेजरी बिलको बोलकबोल

Everything needed for the tracker - instrument type, auction date, tenor and
ISIN - is in that one line. This module pulls it out so the calendar builds
itself from the notices instead of being typed in by hand.
"""

import re

NEP_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

# Nepali month names, all the spellings PDMO actually uses. 1-indexed.
BS_MONTH_NAMES = {
    "बैशाख":1, "वैशाख":1, "baisakh":1,
    "जेठ":2, "जेष्ठ":2, "ज्येष्ठ":2, "jestha":2,
    "असार":3, "आषाढ":3, "अषाढ":3, "ashad":3,
    "साउन":4, "श्रावण":4, "श्रावन":4, "shrawan":4,
    "भदौ":5, "भाद्र":5, "bhadra":5,
    "असोज":6, "आश्विन":6, "अश्विन":6, "ashwin":6,
    "कार्तिक":7, "कात्तिक":7, "kartik":7,
    "मंसिर":8, "मङ्सिर":8, "mangsir":8,
    "पुष":9, "पौष":9, "poush":9,
    "माघ":10, "magh":10,
    "फागुन":11, "फाल्गुन":11, "falgun":11,
    "चैत":12, "चैत्र":12, "chaitra":12,
}

BS_MONTHS = {
 2076:[31,32,31,32,31,31,30,29,30,29,30,30], 2077:[31,31,32,31,31,31,30,29,30,29,30,30],
 2078:[31,31,32,31,31,31,30,29,30,29,30,30], 2079:[31,32,31,32,31,30,30,30,29,29,30,30],
 2080:[31,32,31,32,31,30,30,30,29,29,30,30], 2081:[31,31,32,32,31,30,30,30,29,30,29,31],
 2082:[30,32,31,32,31,30,30,30,29,30,29,31], 2083:[31,31,32,31,31,30,30,30,29,30,29,31],
 2084:[31,31,32,31,31,30,30,30,29,30,29,31], 2085:[31,32,31,32,30,31,30,30,29,30,29,31],
 2086:[30,32,31,32,31,30,30,30,29,30,29,31], 2087:[31,31,32,31,31,31,30,30,29,30,29,31],
 2088:[30,31,32,32,30,31,30,30,29,30,29,31], 2089:[30,32,31,32,31,30,30,30,29,30,29,31],
 2090:[30,32,31,32,31,30,30,30,29,30,29,31],
}


def to_ascii(text):
    return (text or "").translate(NEP_DIGITS)


def bs_to_ad(y, m, d):
    """Bikram Sambat -> ISO date string. m is 1-indexed. Anchor 1 Baisakh 2076 = 14 Apr 2019."""
    from datetime import date, timedelta
    if y not in BS_MONTHS or not (1 <= m <= 12):
        return None
    days = 0
    for yy in range(2076, y):
        if yy not in BS_MONTHS:
            return None
        days += sum(BS_MONTHS[yy])
    days += sum(BS_MONTHS[y][:m-1])
    if d < 1 or d > BS_MONTHS[y][m-1]:
        return None
    days += d - 1
    return (date(2019, 4, 14) + timedelta(days=days)).isoformat()


def find_bs_date(text):
    """Pull a BS date out of a notice title. Returns (y, m, d) or None."""
    t = to_ascii(text)

    # Numeric: 2083।05।01  or  2083-05-01  or  2083/05/01  or  2083.05.01
    m = re.search(r"(20\d\d)\s*[।\-/.]\s*(\d{1,2})\s*[।\-/.]\s*(\d{1,2})", t)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))

    names = "|".join(sorted(BS_MONTH_NAMES, key=len, reverse=True))

    # "2083 भाद्र 24"
    m = re.search(r"(20\d\d)\s*(" + names + r")\s*(\d{1,2})", t, re.I)
    if m:
        mo = BS_MONTH_NAMES.get(m.group(2).lower()) or BS_MONTH_NAMES.get(m.group(2))
        if mo:
            return int(m.group(1)), mo, int(m.group(3))

    # "भाद्र 24, 2083"  /  "24 भाद्र 2083"
    m = re.search(r"(\d{1,2})\s*(" + names + r")\s*,?\s*(20\d\d)", t, re.I)
    if m:
        mo = BS_MONTH_NAMES.get(m.group(2).lower()) or BS_MONTH_NAMES.get(m.group(2))
        if mo:
            return int(m.group(3)), mo, int(m.group(1))
    return None


def classify(text):
    """Treasury Bill, Development Bond, or a savings certificate."""
    t = (text or "").lower()
    if "tbill" in t or "t-bill" in t or "t bill" in t or "ट्रेजरी" in t or "treasury" in t:
        return "Treasury Bill"
    if "विकास ऋणपत्र" in t or "विकास ऋण पत्र" in t or "npdb" in t.lower() \
       or re.search(r"\bdb[- ]?20\d\d", t) or "development bond" in t:
        return "Development Bond"
    if "नागरिक बचतपत्र" in t or "npcb" in t or "citizen saving" in t:
        return "Citizen Savings Bond"
    if "वैदेशिक रोजगार बचतपत्र" in t or "npfb" in t or "foreign employment saving" in t:
        return "Foreign Employment Savings Bond"
    return None


def find_tenor(text):
    """Returns (label, days_equivalent) or (None, None)."""
    t = to_ascii(text)
    m = re.search(r"(\d{1,2})\s*(?:वर्षे|वर्ष|बर्षे|बर्ष|year)", t, re.I)
    if m:
        yrs = int(m.group(1))
        return (f"{yrs} year" if yrs == 1 else f"{yrs} years"), yrs * 365
    m = re.search(r"(\d{2,3})\s*(?:दिने|दिन|day)", t, re.I)
    if m:
        d = int(m.group(1))
        return f"{d} days", d
    return None, None


def find_isin(text):
    m = re.search(r"\b(NP[A-Z]{2}\d{6,10})\b", (text or "").upper())
    return m.group(1) if m else None


def is_auction_notice(text):
    """Auction announcements only - not results, series data or summaries."""
    t = (text or "").lower()
    # Results, historical series and summaries are not upcoming auctions.
    if any(w in t for w in ["result", "नतिजा", "summary", "series", "सिरिज",
                            "time series", "auction result"]):
        return False
    # A cancelled or postponed auction must not sit in the calendar as if live.
    if any(w in t for w in ["रद्द", "स्थगित", "cancel", "postpone"]):
        return False
    return any(w in t for w in ["बोलकबोल", "बिक्री", "निष्कासन", "निष्काशन",
                                "auction", "issue", "bolakbol", "सूचना"])


def extract(items):
    """Turn PDMO news items into calendar entries, newest issue date first."""
    out, seen = [], set()

    for it in items:
        blob = f"{it.get('title','')} {it.get('summary','')}"
        if not is_auction_notice(blob):
            continue

        kind = classify(blob)
        if not kind:
            continue

        bs = find_bs_date(blob)
        if not bs:
            continue
        iso = bs_to_ad(*bs)
        if not iso:
            continue

        label, days = find_tenor(blob)
        isin = find_isin(blob)

        key = (kind, iso, isin or label or "")
        if key in seen:
            continue
        seen.add(key)

        out.append({
            "type": kind,
            # A notice announces the auction date. The issue date is the
            # following day throughout PDMO's published calendar, but it is
            # the plan that states it, so it is not invented here.
            "auction_date": iso,
            "issue_date": iso,
            "bs_auction": f"{bs[0]}-{bs[1]:02d}-{bs[2]:02d}",
            "bs_date": f"{bs[0]}-{bs[1]:02d}-{bs[2]:02d}",
            "tenor": label,
            "tenor_days": days,
            "isin": isin,
            "title": it.get("title", ""),
            "url": it.get("url", ""),
        })

    out.sort(key=lambda x: x["issue_date"], reverse=True)
    return out
