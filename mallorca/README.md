# Lee Shore Mallorca

A single-file web app for picking a boat trip in Mallorca based on where the
wind is coming from. Open `index.html` in a browser — there is no build step,
no dependency and no network call except the Google Fonts stylesheet.

## What it does

Every one of the 32 anchorages in `TRIPS` is stored with the compass direction
its mouth opens onto and the fetch that exposure has to build a sea over. Set
the wind on the rose and the app works out, for each one:

* **Effective sea in the mouth** — the wind component blowing straight in,
  scaled by fetch, turned into a verdict from *Glassy* to *Not today*.
* **Distance** — measured along the coastline polyline rather than straight
  through the island, so rounding Cap de ses Salines costs what it should.
  Offshore islands (Cabrera, Dragonera) run along the shore to the best
  jumping-off point and then strike across.
* **Whether the day fits** — round trip at the cruising speed of the boat you
  picked, plus time at anchor, against the hours you have. Boats also carry a
  sea limit, a range and an absolute wind ceiling, so an unlicensed 15 hp
  rental stays in harbour when it should.

The chart shades each coastline segment by how much of the wind lands on it,
using the segment's own outward normal — so the lee shore is visible at a
glance rather than being something you work out per cove.

## Editing the data

Everything lives in the `<script>` block at the bottom of `index.html`:

| Constant | What it holds |
|---|---|
| `WINDS` | the eight winds and their Mallorquí names |
| `PORTS` | departure harbours with coordinates |
| `BOATS` | speed, sea limit, range, wind ceiling |
| `TRIPS` | the anchorages: `face`, `fetch`, `ashore`, copy, anchoring notes |
| `COAST` | coastline vertices used for distances and exposure shading |

To add a trip, copy an existing entry and set `face` to the direction the
anchorage *opens onto* (wind from that bearing blows straight in) and `fetch`
to roughly 0.8 for a pocket inside a bay, 1.0 for open coast, 1.3 for
something looking at open sea.

Settings and saved trips persist in `localStorage`.

## Caveat

Planning aid, not a chart. Distances are schematic, the coastline is
simplified, and headlands accelerate wind well beyond the number on the
slider. Check a real forecast before you leave.
