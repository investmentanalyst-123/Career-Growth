"""
Annual issuance plan reader.

PDMO publishes the year's full auction calendar as a PDF, listed at
https://pdmo.gov.np/category/annualous-loan-schedule/ . Each Shrawan a new
one appears for the new fiscal year, and revisions can appear mid-year.
This module finds the newest one automatically, downloads it and reads the
schedule out, so the tracker refreshes itself when the plan changes.

Row structure in the PDF, one instrument per line:

    <no> <instrument> <tenor> <rate text> <auction date> <issue date> <amount>
    1    ट्रेजरी बिल   ९१ दिने  बोलकबोल...  6/5/2083      6/6/2083     ५००

The instrument names extract badly because of the embedded font, so
classification uses the tenor unit instead, which is reliable: treasury
bills are always quoted in days, development bonds always in years.
Dates are Bikram Sambat in M/D/YYYY.
"""

import re
from datetime import date, timedelta

NEP_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

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

# Rows for savings certificates are laid out differently and are not auctions.
SAVINGS_MARKERS = ["बचतपर", "बचतपत्र", "नागररक", "नागरिक", "र्ैदेखिक", "वैदेशिक", "देखख", "देखि"]


def to_ascii(t):
    return (t or "").translate(NEP_DIGITS)


def bs_to_ad(y, m, d):
    if y not in BS_MONTHS or not (1 <= m <= 12):
        return None
    if d < 1 or d > BS_MONTHS[y][m - 1]:
        return None
    days = sum(sum(BS_MONTHS[yy]) for yy in range(2076, y) if yy in BS_MONTHS)
    if any(yy not in BS_MONTHS for yy in range(2076, y)):
        return None
    days += sum(BS_MONTHS[y][:m - 1]) + d - 1
    return (date(2019, 4, 14) + timedelta(days=days)).isoformat()


# <no> ... <n> <days|years unit> ... <M/D/YYYY> <M/D/YYYY> <amount>
ROW = re.compile(
    r"(\d{1,3})\s*"                                  # tenor number
    r"(ददने|दिने|दद ने|र्षे|वर्षे|वषे|बर्षे)"          # unit: days or years
    r"[^\d]*?"                                       # rate wording
    r"(\d{1,2})/(\d{1,2})/(20\d\d)"                  # auction date
    r"\s+(\d{1,2})/(\d{1,2})/(20\d\d)"               # issue date
    r"\s*([\d,\.]*)"                                 # amount, may be absent
)

DAY_UNITS = {"ददने", "दिने", "दद ने"}


# A row whose tenor is present but whose dates are missing has wrapped onto
# the following line in the PDF. Detect that so the row is not lost.
TENOR_ONLY = re.compile(r"\d{1,3}\s*(ददने|दिने|दद ने|र्षे|वर्षे|वषे|बर्षे)")
HAS_DATES  = re.compile(r"\d{1,2}/\d{1,2}/20\d\d\s+\d{1,2}/\d{1,2}/20\d\d")


def join_wrapped(text):
    """Stitch a tenor line back together with the date line beneath it."""
    lines = (text or "").splitlines()
    out, i = [], 0
    while i < len(lines):
        cur = lines[i]
        if (TENOR_ONLY.search(to_ascii(cur))
                and not HAS_DATES.search(to_ascii(cur))
                and i + 1 < len(lines)
                and HAS_DATES.search(to_ascii(lines[i + 1]))):
            out.append(cur.rstrip() + " " + lines[i + 1].strip())
            i += 2
            continue
        out.append(cur)
        i += 1
    return "\n".join(out)


def parse_text(text):
    """Read plan rows out of the PDF's extracted text."""
    out = []
    for raw in join_wrapped(text).splitlines():
        line = to_ascii(raw)
        if any(m in raw for m in SAVINGS_MARKERS):
            continue                                   # savings bonds, not auctions
        m = ROW.search(line)
        if not m:
            continue

        n, unit = int(m.group(1)), m.group(2)
        is_days = unit in DAY_UNITS

        a_iso = bs_to_ad(int(m.group(5)), int(m.group(3)), int(m.group(4)))
        i_iso = bs_to_ad(int(m.group(8)), int(m.group(6)), int(m.group(7)))
        if not i_iso:
            continue

        amount = None
        raw_amt = (m.group(9) or "").replace(",", "").split(".")[0]
        if raw_amt.isdigit() and int(raw_amt):
            amount = f"Rs {int(raw_amt):,} crore"

        out.append({
            "type": "Treasury Bill" if is_days else "Development Bond",
            "tenor": f"{n} days" if is_days else (f"{n} year" if n == 1 else f"{n} years"),
            "tenor_days": n if is_days else n * 365,
            "auction_date": a_iso,
            "issue_date": i_iso,
            "bs_date": f"{m.group(8)}-{int(m.group(6)):02d}-{int(m.group(7)):02d}",
            "bs_auction": (f"{m.group(5)}-{int(m.group(3)):02d}-{int(m.group(4)):02d}"
                           if a_iso else None),
            "amount": amount,
            "planned": True,
            "isin": None,
        })

    # Same instrument on the same day listed twice is a duplicate row.
    seen, uniq = set(), []
    for e in out:
        k = (e["type"], e["tenor"], e["issue_date"])
        if k not in seen:
            seen.add(k)
            uniq.append(e)
    uniq.sort(key=lambda x: x["issue_date"])
    return uniq


def dedupe(entries):
    """Same instrument, tenor and issue date is the same auction."""
    seen, out = set(), []
    for e in sorted(entries, key=lambda x: x["issue_date"]):
        k = (e["type"], e["tenor"], e["issue_date"])
        if k in seen:
            continue
        seen.add(k)
        out.append(e)
    return out


# Treasury bill tenors are always one of these. Development bonds are quoted
# in years and are never this long. So a row can be classified from the number
# alone, without reading the Nepali word for "days" - which is what the PDF's
# embedded font mangles.
TBILL_DAYS = {28, 35, 42, 56, 63, 77, 91, 182, 273, 364}
BOND_YEARS = set(range(1, 31))

LOOSE = re.compile(
    r"(\d{1,3})\s*[^\d/]{0,40}?"
    r"(\d{1,2})\s*[/\-.।]\s*(\d{1,2})\s*[/\-.।]\s*(20\d\d)"
    r"\s*[^\d]{0,6}"
    r"(\d{1,2})\s*[/\-.।]\s*(\d{1,2})\s*[/\-.।]\s*(20\d\d)"
    r"\s*([\d,\.]*)"
)


def parse_loose(text):
    """
    Last-resort reader that ignores the instrument wording entirely.

    A schedule row is: a tenor number, then two Bikram Sambat dates, then an
    amount. That shape survives any font problem. The tenor number alone says
    which instrument it is - 91 or 182 or 364 is a treasury bill, 5 or 12 is
    a bond - so nothing depends on reading mangled Devanagari.
    """
    out = []
    for raw in join_wrapped(text).splitlines():
        if any(m in raw for m in SAVINGS_MARKERS):
            continue
        line = to_ascii(raw)
        m = LOOSE.search(line)
        if not m:
            continue

        n = int(m.group(1))
        if n in TBILL_DAYS:
            is_days = True
        elif n in BOND_YEARS:
            is_days = False
        else:
            continue

        a_iso = bs_to_ad(int(m.group(4)), int(m.group(2)), int(m.group(3)))
        i_iso = bs_to_ad(int(m.group(7)), int(m.group(5)), int(m.group(6)))
        if not i_iso:
            continue

        amount = None
        raw_amt = (m.group(8) or "").replace(",", "").split(".")[0]
        if raw_amt.isdigit() and 10 <= int(raw_amt) <= 100000:
            amount = f"Rs {int(raw_amt):,} crore"

        out.append({
            "type": "Treasury Bill" if is_days else "Development Bond",
            "tenor": f"{n} days" if is_days else (f"{n} year" if n == 1 else f"{n} years"),
            "tenor_days": n if is_days else n * 365,
            "auction_date": a_iso,
            "issue_date": i_iso,
            "bs_date": f"{m.group(7)}-{int(m.group(5)):02d}-{int(m.group(6)):02d}",
            "bs_auction": f"{m.group(4)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if a_iso else None,
            "amount": amount,
            "planned": True,
            "isin": None,
        })
    return out


def pick_latest(rows):
    """
    Choose which published plan to use.

    Rows come from the schedule page as (title, pdf_url). The newest fiscal
    year wins; within a year a revised plan beats the original. This is what
    makes next Shrawan's plan get picked up without anyone touching the code.
    """
    best, best_key = None, None
    for title, url in rows:
        t = to_ascii(title or "")
        m = re.search(r"(20\d\d)\s*/\s*(\d{2,4})", t)
        if not m:
            continue
        year = int(m.group(1))
        revised = 1 if ("संशोधित" in (title or "") or "revis" in t.lower()) else 0
        key = (year, revised)
        if best_key is None or key > best_key:
            best, best_key = (title, url), key
    return best


# ------------------------------------------------------------- collection

SCHEDULE_PAGE = "https://pdmo.gov.np/category/annualous-loan-schedule/"


def links_from_page(html, base=SCHEDULE_PAGE):
    """Pull (title, pdf_url) pairs out of the schedule listing table."""
    from urllib.parse import urljoin
    from bs4 import BeautifulSoup

    rows = []
    soup = BeautifulSoup(html, "html.parser")
    for tr in soup.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 2:
            continue
        title = " ".join(cells[1].get_text(" ").split())
        pdf = None
        for a in tr.find_all("a", href=True):
            if ".pdf" in a["href"].lower():
                pdf = urljoin(base, a["href"])
                break
        if title and pdf:
            rows.append((title, pdf))

    # Fall back to any PDF link on the page if the table markup changes.
    if not rows:
        for a in soup.find_all("a", href=True):
            if ".pdf" in a["href"].lower():
                label = " ".join(a.get_text(" ").split()) or a["href"]
                rows.append((label, urljoin(base, a["href"])))
    return rows


def pdf_to_tables(data):
    """
    Pull the schedule out as real table rows.

    The plan is a bordered table, so reading the cells directly is far more
    reliable than parsing flowed text: a row never gets split across lines
    and a column never runs into its neighbour. Text parsing stays as a
    fallback for the day the layout changes.
    """
    rows = []
    try:
        import io, pdfplumber
        with pdfplumber.open(io.BytesIO(data)) as doc:
            for page in doc.pages:
                for table in (page.extract_tables() or []):
                    for row in table:
                        cells = [(c or "").replace("\n", " ").strip() for c in row]
                        if any(cells):
                            rows.append(cells)
    except Exception:
        return []
    return rows


DATE_CELL = re.compile(r"^\s*(\d{1,2})\s*[/\-.।]\s*(\d{1,2})\s*[/\-.।]\s*(20\d\d)\s*$")
TENOR_CELL = re.compile(r"(\d{1,3})\s*(ददने|दिने|दद ने|र्षे|वर्षे|वषे|बर्षे)")


def parse_tables(rows):
    """Read auction rows out of extracted table cells."""
    out = []
    for cells in rows:
        ascii_cells = [to_ascii(c) for c in cells]

        # Savings certificates sit in the same table but are not auctions.
        if any(m in " ".join(cells) for m in SAVINGS_MARKERS):
            continue

        tenor = None
        for c in ascii_cells:
            m = TENOR_CELL.search(c)
            if m:
                tenor = (int(m.group(1)), m.group(2))
                break
        if not tenor:
            continue

        dates = []
        for c in ascii_cells:
            m = DATE_CELL.match(c)
            if m:
                dates.append((int(m.group(3)), int(m.group(1)), int(m.group(2))))
        if len(dates) < 2:
            continue

        n, unit = tenor
        is_days = unit in DAY_UNITS
        a_iso = bs_to_ad(*dates[0])
        i_iso = bs_to_ad(*dates[1])
        if not i_iso:
            continue

        amount = None
        for c in reversed(ascii_cells):
            raw = c.replace(",", "").split(".")[0].strip()
            if raw.isdigit() and 10 <= int(raw) <= 100000:
                amount = f"Rs {int(raw):,} crore"
                break

        out.append({
            "type": "Treasury Bill" if is_days else "Development Bond",
            "tenor": f"{n} days" if is_days else (f"{n} year" if n == 1 else f"{n} years"),
            "tenor_days": n if is_days else n * 365,
            "auction_date": a_iso,
            "issue_date": i_iso,
            "bs_date": f"{dates[1][0]}-{dates[1][1]:02d}-{dates[1][2]:02d}",
            "bs_auction": f"{dates[0][0]}-{dates[0][1]:02d}-{dates[0][2]:02d}" if a_iso else None,
            "amount": amount,
            "planned": True,
            "isin": None,
        })
    return out


def pdf_to_text(data):
    """Extract text from PDF bytes. Tries pdfplumber, then pypdf."""
    try:
        import io, pdfplumber
        with pdfplumber.open(io.BytesIO(data)) as doc:
            return "\n".join((pg.extract_text() or "") for pg in doc.pages)
    except Exception:
        pass
    try:
        import io
        from pypdf import PdfReader
        return "\n".join((pg.extract_text() or "") for pg in PdfReader(io.BytesIO(data)).pages)
    except Exception:
        return ""


def collect(fetch, log=print):
    """
    Fetch the newest published plan and return its auction rows.

    'fetch' is the collector's own HTTP function so retries, timeouts and the
    certificate workaround for government sites are shared. Any failure here
    returns an empty list - the tracker then shows confirmed auctions only,
    rather than the whole run breaking.
    """
    try:
        page = fetch(SCHEDULE_PAGE)
        if page is None:
            log("  annual plan: schedule page did not respond")
            return [], None

        rows = links_from_page(page.content.decode("utf-8", "ignore"))
        if not rows:
            log("  annual plan: no PDF links found on the schedule page")
            return [], None

        chosen = pick_latest(rows) or rows[0]
        title, url = chosen
        log(f"  annual plan: {title[:64]}")

        doc = fetch(url)
        if doc is None:
            log("  annual plan: PDF download failed")
            return [], None

        # Table extraction first, text parsing as a safety net. Whichever
        # recovers more rows wins, so a layout change degrades instead of
        # silently dropping half the calendar.
        raw_text = pdf_to_text(doc.content)
        by_table = dedupe(parse_tables(pdf_to_tables(doc.content)))
        by_text  = dedupe(parse_text(raw_text))
        by_loose = dedupe(parse_loose(raw_text))

        def tb(x): return sum(1 for e in x if e["type"] == "Treasury Bill")
        log(f"  annual plan: table {len(by_table)} rows ({tb(by_table)} TB), "
            f"text {len(by_text)} rows ({tb(by_text)} TB), "
            f"loose {len(by_loose)} rows ({tb(by_loose)} TB)")

        # Three independent readings, merged. A row any one of them recovers
        # is kept, so no single extraction quirk can empty the calendar.
        entries = dedupe(by_table + by_text + by_loose)

        if not entries and raw_text:
            log("  annual plan: nothing matched. First lines of the PDF text, "
                "so the pattern can be checked:")
            for ln in [l for l in raw_text.splitlines() if l.strip()][:12]:
                log(f"      | {ln[:110]}")
        tb = sum(1 for e in entries if e["type"] == "Treasury Bill")
        db = len(entries) - tb
        log(f"  annual plan: {len(entries)} scheduled auction(s) "
            f"({tb} treasury bills, {db} development bonds)")
        return entries, title
    except Exception as e:
        log(f"  annual plan failed: {type(e).__name__}: {e}")
        return [], None
