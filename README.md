# Career Growth

A daily briefing site for a chartered accountant working in Nepal. It collects
headlines from your regulators, financial press and technology sources every
morning before 6:00, and keeps a Skills tab for career development.

Runs at zero cost on GitHub. Nothing to install on your computer.

---

## Setup — about 15 minutes

### 1. Create the repository

Sign in at github.com, click **+** in the top right, then **New repository**.

- Name it `career-growth`
- Set it to **Public** (this is what makes Actions and Pages free)
- Do **not** tick "Add a README"
- Click **Create repository**

### 2. Upload the files

On the empty repository page, click **uploading an existing file**.

Drag in everything from this folder. Important: drag the *contents*, keeping
the folder structure. The final layout must be:

```
index.html
skills.js
scraper.py
sources.json
requirements.txt
data/news.json
.github/workflows/daily-update.yml
```

If the `.github` folder does not upload through the browser, see
"If .github will not upload" at the bottom.

Click **Commit changes**.

### 3. Turn on the website

**Settings** → **Pages** (left sidebar) → under Source choose **Deploy from a
branch** → Branch **main**, folder **/ (root)** → **Save**.

Wait two minutes. Your site is at:

```
https://YOUR-USERNAME.github.io/career-growth/
```

Bookmark it. This is the address you open every morning.

### 4. Run the collector once

**Actions** tab → if it asks, click **I understand my workflows, go ahead and
enable them** → click **Morning update** in the left list → **Run workflow** →
**Run workflow**.

Give it two to four minutes. Refresh your site. The sample data is replaced
with live headlines.

From then on it runs by itself at 05:30 every morning.

---

## Reading the results

Click into the run under the Actions tab and open **Collect the news**. The log
lists every source and what it found:

```
  -> ICAN
     8 items via page scrape  (3.2s)
  -> Nepal Rastra Bank
     nothing found  (12.1s)
```

At the bottom it prints two useful lists: sources that failed, and any RSS
feeds it discovered. If it found a feed, paste that URL into the `"rss"` field
for that source in `sources.json` — future runs will be faster and more
reliable.

The left panel on the website shows the same information as a green or grey dot
per source, so you can see at a glance whether something has quietly broken.

---

## Expect some sources to fail at first

There are 32 sources configured. On the first run, expect roughly half to work
immediately. That is normal, not a fault. Sites fail for three reasons:

**The page loads content with JavaScript.** The scraper reads the HTML that
arrives; if the headlines are painted in afterwards by a script, there is
nothing to read. Common on stock and dashboard pages.

**The site blocks automated visitors.** Some government sites reject anything
that is not a person clicking.

**The scraper found the wrong part of the page** — a menu instead of the
articles. This one is fixable and usually easy.

### Fixing a source

Open the site in Chrome, right-click a headline, choose **Inspect**. Look for
the container holding the article list — something like
`<div class="news-list">`. Then in `sources.json` set:

```json
"selector": ".news-list"
```

Commit the change and run the workflow again. That narrows the scrape to the
right region.

If a site genuinely cannot be read, delete it from `sources.json` and check it
manually. Better to have twenty reliable sources than thirty-two noisy ones.

### Testing on your own computer (optional)

If you install Python you can test without waiting for the schedule:

```bash
pip install -r requirements.txt
python scraper.py --only ican --verbose
```

The `--verbose` flag shows every URL tried and why it failed.

---

## Things you will want to edit

**Add or remove sources** — `sources.json`. Copy an existing block, change the
`id`, `name`, `url` and `category`. The `id` must be unique.

**Compliance deadlines** — near the top of the script section in `index.html`,
find `const DEADLINES`. Dates are Gregorian on purpose so there is no
ambiguity. `monthly: 10` repeats on the 10th of every month. The four entries
there now are placeholders based on common filing dates — replace them with
your actual obligations and client deadlines.

**Skills and courses** — `skills.js`. Each entry has a name, a one-line reason,
and its links. The YouTube links are pre-loaded searches rather than specific
video IDs, because video IDs die and a dead link in a study plan is worse than
no link. When you find a course you like, paste its real URL over the search
link.

**The change time** — in `.github/workflows/daily-update.yml`, the line
`cron: "45 23 * * *"`. That is 23:45 UTC, which is 05:30 in Kathmandu. To move
it, subtract 5 hours 45 minutes from the Nepal time you want.

**Keywords that flag an item as "Key"** — `PRIORITY_TERMS` in `scraper.py`.
It already covers English and Nepali terms like circular, directive, परिपत्र
and सूचना. Add the terms that matter in your practice.

---

## Notes

**The Nepali date.** Calculated in the browser from a Bikram Sambat table
covering 2076–2090. Check it against Hamro Patro on your first morning. If it
is off, the table is `BS_MONTHS` in `index.html`. Deadlines deliberately use
Gregorian dates, so even if the displayed Nepali date were wrong by a day, no
deadline calculation is affected.

**Opening index.html by double-clicking will not load the news.** Browsers
block `fetch` on `file://` addresses. It works normally once served over
GitHub Pages, which is how you will actually use it.

**Read/unread marks and skill progress** live in your browser, not on the
server. They are per-device, and clearing browser data clears them.

**Scheduled runs stop after 60 days of repository inactivity** on free
accounts. The workflow commits the news file each morning, which counts as
activity, so this will not happen while it is running normally.

**Timing.** GitHub's scheduler can run 5–20 minutes late when their servers are
busy. That is why it is set for 05:30 rather than 06:00.

**Everything the site shows is a headline and a link.** It does not copy
article text — it points you at the source, which is both the correct way to
treat other people's publishing and the only way to be sure you are reading the
authoritative version of a circular.

---

## If .github will not upload

GitHub's browser uploader sometimes skips folders beginning with a dot. Create
the file directly instead:

1. On the repository page click **Add file** → **Create new file**
2. In the filename box type: `.github/workflows/daily-update.yml`
   (typing the slashes creates the folders)
3. Paste the contents of `daily-update.yml` from this folder
4. **Commit changes**
