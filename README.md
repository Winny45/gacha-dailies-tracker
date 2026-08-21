# Gacha Dailies Tracker

Tracks daily/weekly checklists and upcoming events/banners for NIKKE, Blue
Archive, Limbus Company, and Brown Dust 2.

Two front-ends, one set of scrapers:

| | What it is | Where the data comes from |
|---|---|---|
| **Desktop** | Python + PySide6 app (`app.py`) | scrapes live when you hit Refresh |
| **Phone** | installable web app in `web/` | reads JSON published by GitHub Actions |

---

## Putting it on your phone

The desktop app can't be ported to Android — Qt's Android deployment is
experimental and `lxml` (a C extension) would need ARM cross-compilation.
So the phone gets a **PWA**: a web app that installs to the home screen
with its own icon, runs fullscreen with no browser chrome, and works
offline. It reuses the same Python scrapers via `build_web.py`.

### One-time setup

1. Create an empty repo on GitHub (any name, public — Pages is free for
   public repos).
2. From this folder, push:

```bash
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPO.git
```

```bash
git push -u origin main
```

3. In the repo: **Settings → Pages → Build and deployment → Source →
   GitHub Actions**.
4. Open the **Actions** tab and let the "Update data & deploy" workflow
   run (or trigger it with *Run workflow*).
5. On your phone, open `https://YOUR-USERNAME.github.io/YOUR-REPO/`, then
   Chrome menu → **Add to Home screen**.

After that it behaves like any installed app. The workflow re-scrapes and
redeploys **every day at 06:00 UTC**, so the phone stays current without
you doing anything — that's why its ⟳ button just reloads the published
data rather than scraping (phone browsers can't scrape those sites
directly; none of them send CORS headers).

### Notes

- **Checklists are per device.** Ticking something on the phone doesn't
  update the desktop app, by design — no account or server needed.
- The phone app ships only the portraits for banners that are live or
  upcoming (~1 MB total) rather than the whole image cache.
- If a source is down when the workflow runs, that game keeps its last
  published data instead of going blank.

### Running the phone app locally (optional)

```bash
.venv\Scripts\python.exe build_web.py
```

```bash
.venv\Scripts\python.exe -m http.server 8765 --directory web
```

Then visit `http://localhost:8765`.

---

## Running the desktop app

Double-click **`Launch Gacha Dailies Tracker.bat`**, or run it manually:

```
.venv\Scripts\python.exe app.py
```

(the venv already has PySide6, requests, beautifulsoup4, lxml, feedparser,
and python-dateutil installed)

## How it works

- **Each game has a tab icon** (its Play Store icon, downloaded once into
  `assets/icons/`).
- **Dailies/weeklies tab per game** — checkboxes persist in
  `user_data/checklist_state.json` and automatically go back to unchecked
  after that game's actual daily/weekly reset time (see `data/games.py` for
  each game's reset schedule, task list, and per-task time estimate).
- **Time remaining** — each game tab (and the Today tab, summed across all
  games) shows a running total of estimated minutes for everything not yet
  checked off. It recalculates the instant you tick a box, so it counts down
  as you clear tasks.
- **Current vs. Upcoming** — each game's events/banners are split into what's
  live right now vs. what's coming next, both sorted soonest-first. Banners
  show a character portrait thumbnail next to them; anything without one
  (or with an image still downloading) falls back to that game's icon
  instead of a blank box.
- **"Today" tab** — cross-game view of what's still due, the overall time
  remaining, and current/upcoming events across all four games.
- **"[Game] Banner Guide" button** on each game tab — opens a dialog showing
  just that game's current/upcoming character banners. Inside it,
  **"Refresh Analysis"** fetches every tier-list/review source available
  for that game, normalizes each one's rating onto a shared 0–5 scale, and
  averages them into a single consensus badge (**Strong Pull / Good Pull /
  Situational / Low Priority-Skip**) — with every individual source listed
  underneath, so you can see disagreement rather than have it hidden.
  Results cache to `user_data/consensus_cache.json` and persist until you
  refresh again.

  There is **no AI involved** — the consensus is a plain average of what
  the sources actually say. Sources whose label doesn't map to a tier
  (e.g. Brown Dust 2's "FH/GR Regular", "New Character") are still shown,
  they just don't move the number. A character no source has rated yet
  (common for brand-new collab units) honestly shows "No consensus data"
  rather than a guess.
- **"Refresh events & banners from the web" button** — runs the scrapers in
  `scrapers/` against community wikis/trackers for each game, caches the
  results in `user_data/events_cache.json`, and downloads any new character
  portraits into `user_data/image_cache/`. Cached data is shown immediately
  on launch; nothing hits the network until you click Refresh.

## Data sources per game

| Game | Events/banners | Portraits | Pull-verdict sources compared |
|---|---|---|---|
| NIKKE | hostedgg.com | prydwen.gg character roster | hostedgg "Should you pull?" writeup · Pocket Tactics tier · **Prydwen** tier (SSS–F) |
| Blue Archive | bluearchive.wiki | bluearchive.wiki banner images | Pocket Gamer tier · Game.Guide writeup · Pocket Tactics tier |
| Limbus Company | limbuscompany.wiki.gg | limbuscompany.wiki.gg | Pocket Tactics tier · **Prydwen** numeric rating (x/10) |
| Brown Dust 2 | gamependium.com | gamependium.com | gamependium Recommended/Skip + writeup · Pocket Gamer tier + writeup · **BD2 Banner Recommendation** priority + reason + pros/cons + per-mode ratings |

[BD2 Banner Recommendation](https://zormolo.github.io/BD2-Banner-Recommendation/)
(by Zormolo & Botan) is the richest single source of the lot: the page
itself is client-rendered, but it serves its data as a plain JSON file, so
the app reads that directly instead of scraping HTML. Each banner comes
with a pull priority, a written reason, explicit **pros and cons** lists
(shown as green/red bullets in the Banner Guide), and per-game-mode ratings
(GR/FH/LN/ToS/MW/GC).

Prydwen only covers NIKKE and Limbus Company — it has no Blue Archive or
Brown Dust 2 section, so those two use the other sources listed. The two
Prydwen pages need different handling and are parsed differently: the
NIKKE tier list is server-rendered HTML, while the Limbus one renders
client-side and its ratings have to be lifted out of the page's embedded
Next.js data payload instead (see `scrapers/consensus.py`).

Blue Archive's banner list also excludes the standard 10+-character
"choose one" recruitment pool banners (identified by their `data-type`
attribute on the source page, not by guessing from the title) -- those
aren't real character banners.

These are community sites, not official APIs — none of the four games
expose one, and the tier-list/verdict sources in particular are one
person's/site's opinion, not a guarantee. Fuzzy name-matching (used for
NIKKE and Limbus, where the banner source and the verdict source don't use
identical names) can occasionally miss or mismatch on a very new or
oddly-named character -- when that happens the app just shows no verdict
rather than a guess.

If a source changes its page layout, that game's scraper may start
returning 0 new events/verdicts; the app just keeps showing the last
successful cache rather than crashing. If that happens, the fix is updating
the selectors in the matching `scrapers/<game>.py` file.

## Updating the static data

Reset times and the recurring task lists rarely change — they're hardcoded
in `data/games.py` with source notes in the comments. If a game reworks its
daily/weekly systems, edit that file directly.
