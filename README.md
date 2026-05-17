# Sapta Sankalp — 7 Appeals Tracker

An observational tracker of publicly available market and macro indicators
related to the seven appeals made by PM Modi on 10 May 2026 under the
theme "Nation First, Duty Above Comfort."

The site is intentionally non-partisan: it presents data and does not
interpret whether the appeals have "worked."

**Live site:** _[set this once GitHub Pages is enabled]_

## What this repo contains

```
index.html                       The site (single static HTML file)
data/
  prices.json                    Daily-updated price series (committed by bot)
  fuel-prices.json               Manually-maintained retail fuel prices
scripts/
  fetch.py                       Daily data fetcher
.github/workflows/
  update.yml                     Daily cron — runs fetch.py and commits
requirements.txt                 Python dependencies
HOSTING_GUIDE.md                 Step-by-step deploy instructions
```

## How it works

1. `scripts/fetch.py` runs daily on GitHub Actions at 17:00 IST.
2. It pulls closing prices from Yahoo Finance, India CPI from FRED,
   and merges retail fuel prices from `data/fuel-prices.json`.
3. It writes `data/prices.json` and a workflow step commits the change.
4. GitHub Pages serves the static `index.html`, which fetches `prices.json`
   on page load and renders the chart.

## Updating fuel prices

Retail petrol, diesel, and LPG prices are administered and revise
infrequently. Edit `data/fuel-prices.json` and append a new
`[YYYY-MM-DD, value]` row in the relevant series when a revision is
announced. The site carries the last known value forward between updates.

## Sources

- Yahoo Finance (equities, indices, commodities, currencies)
- FRED · St. Louis Fed (India CPI, series `INDCPIALLMINMEI`)
- IOCL daily RSP (manually transcribed into `fuel-prices.json`)
- MyGov (verbatim speech text)

## Setting it up

See `HOSTING_GUIDE.md` for a step-by-step beginner walkthrough.
