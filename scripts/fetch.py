"""
fetch.py — Sapta Sankalp data fetcher.

Pulls daily closes for all tracked instruments from Yahoo Finance,
scrapes Mumbai retail fuel prices from goodreturns.in, reads manual
fuel and CPI overrides, computes a synthetic equal-weighted fertilizer
index, forward-fills slow-moving series, and writes the combined dataset
to data/prices.json.

Run daily via GitHub Actions (see .github/workflows/update.yml).
"""

import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from io import StringIO
from pathlib import Path

import yfinance as yf
import pandas as pd
import requests

# ============================================================
# Config
# ============================================================

SPEECH_DATE = "2026-05-10"
REBASE_DATE = "2026-05-08"
FETCH_START = "2026-05-08"

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
OUTPUT_FILE = DATA_DIR / "prices.json"
FUEL_INPUT_FILE = DATA_DIR / "fuel-prices.json"
CPI_INPUT_FILE = DATA_DIR / "cpi.json"

YAHOO_INSTRUMENTS = {
    "cnxit":       "^CNXIT",
    "cnxrealty":   "^CNXREALTY",
    "cnxauto":     "^CNXAUTO",
    "goldbees":    "GOLDBEES.NS",
    "gc":          "GC=F",
    "brent":       "BZ=F",
    "cnxenergy":   "^CNXENERGY",
    "ioc":         "IOC.NS",
    "bpcl":        "BPCL.NS",
    "awl":         "AWL.NS",
    "patanjali":   "PATANJALI.NS",
    "coromandel":  "COROMANDEL.NS",
    "fact":        "FACT.NS",
    "chambal":     "CHAMBLFERT.NS",
    "deepakfert":  "DEEPAKFERT.NS",
    "paradeep":    "PARADEEP.NS",
    "cnxfmcg":     "^CNXFMCG",
    "indhotel":    "INDHOTEL.NS",
    "indigo":      "INDIGO.NS",
    # Nifty India Tourism — try multiple ticker variants; yfinance picks whichever has data
    "tourism":     "^CNXTOURISM",
    "usdinr":      "USDINR=X",
    "nifty50":     "^NSEI",
    "niftymid":    "^NSEMDCP50",
    "niftysml":    "^CNXSC",
    "nifty500":    "^CRSLDX",
}

FERT_INDEX_COMPONENTS = ["coromandel", "fact", "chambal", "deepakfert", "paradeep"]

GOODRETURNS_URLS = {
    "petrol_mum":  "https://www.goodreturns.in/petrol-price-in-mumbai.html",
    "diesel_mum":  "https://www.goodreturns.in/diesel-price-in-mumbai.html",
    "lpg_dom_mum": "https://www.goodreturns.in/lpg-price-in-mumbai.html",
    "lpg_com_mum": "https://www.goodreturns.in/lpg-price-in-mumbai.html",
}

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-User": "?1",
    "Sec-Fetch-Dest": "document",
}

# ============================================================
# Fetchers
# ============================================================

def fetch_yahoo(start_date: str):
    results = {}
    tickers = list(YAHOO_INSTRUMENTS.values())
    print(f"[yahoo] Fetching {len(tickers)} tickers from {start_date}...")

    df = yf.download(
        tickers=tickers,
        start=start_date,
        end=None,
        group_by="ticker",
        auto_adjust=False,
        progress=False,
        threads=True,
    )

    for iid, ticker in YAHOO_INSTRUMENTS.items():
        try:
            if len(tickers) == 1:
                series = df["Close"]
            else:
                series = df[ticker]["Close"]
            series = series.dropna()
            pairs = []
            for idx, val in series.items():
                d = pd.Timestamp(idx).strftime("%Y-%m-%d")
                pairs.append([d, round(float(val), 4)])
            if pairs:
                results[iid] = pairs
                print(f"  OK  {iid:14s} {ticker:25s} {len(pairs):4d} closes (latest {pairs[-1][0]} @ {pairs[-1][1]})")
            else:
                print(f"  --  {iid:14s} {ticker:25s} no data")
        except Exception as e:
            print(f"  XX  {iid:14s} {ticker:25s} {e}")
    return results


def _parse_goodreturns_table(html, month_year_hint=None):
    """
    Goodreturns pages contain a table of recent daily prices like:
        Date        Price   Change
        16 May 2026 106.68  +3.14
        15 May 2026 103.54  0.00
        ...
    Returns list of [YYYY-MM-DD, float] pairs, newest-first.
    """
    # Match rows: DD Mon YYYY  price
    pattern = re.compile(
        r'(\d{1,2})\s+([A-Z][a-z]+)\s+(\d{4})'   # date
        r'[\s\S]{1,80}?'                            # separator cells
        r'([\d]+\.[\d]{2})',                         # price value
        re.MULTILINE
    )
    month_map = {
        'Jan':1,'Feb':2,'Mar':3,'Apr':4,'May':5,'Jun':6,
        'Jul':7,'Aug':8,'Sep':9,'Oct':10,'Nov':11,'Dec':12
    }
    results = []
    seen = set()
    for m in pattern.finditer(html):
        try:
            day, mon_str, year = int(m.group(1)), m.group(2), int(m.group(3))
            mon = month_map.get(mon_str[:3])
            if not mon or year < 2026:
                continue
            iso = f"{year}-{mon:02d}-{day:02d}"
            price = float(m.group(4))
            if iso not in seen and price > 0:
                results.append([iso, price])
                seen.add(iso)
        except Exception:
            continue
    return sorted(results, key=lambda x: x[0])


def scrape_goodreturns():
    """Scrape historical daily prices for Mumbai from goodreturns.in.
    Returns dict {iid: [[YYYY-MM-DD, price], ...]} for each fuel type."""
    print("[goodreturns] Scraping Mumbai fuel prices (historical table)...")
    results = {}
    session = requests.Session()
    session.headers.update(BROWSER_HEADERS)

    def fetch_html(url):
        r = session.get(url, timeout=25)
        r.raise_for_status()
        return r.text

    # Petrol
    try:
        html = fetch_html(GOODRETURNS_URLS["petrol_mum"])
        pairs = _parse_goodreturns_table(html)
        if pairs:
            results["petrol_mum"] = pairs
            print(f"  OK petrol_mum: {len(pairs)} obs, latest {pairs[-1]}")
        else:
            print(f"  XX petrol_mum: table parse returned nothing")
    except Exception as e:
        print(f"  XX petrol_mum: {e}")

    # Diesel
    try:
        html = fetch_html(GOODRETURNS_URLS["diesel_mum"])
        pairs = _parse_goodreturns_table(html)
        if pairs:
            results["diesel_mum"] = pairs
            print(f"  OK diesel_mum: {len(pairs)} obs, latest {pairs[-1]}")
        else:
            print(f"  XX diesel_mum: table parse returned nothing")
    except Exception as e:
        print(f"  XX diesel_mum: {e}")

    # LPG — both on the same page; domestic 14.2kg and commercial 19kg prices are on
    # the LPG history page; we extract two parallel series
    try:
        html = fetch_html(GOODRETURNS_URLS["lpg_dom_mum"])
        # The LPG page typically has one table for domestic and one for commercial
        # Split into two halves around a 'Commercial' section header
        dom_section = html
        com_section = html
        if 'commercial' in html.lower() or 'Commercial' in html:
            idx = max(html.lower().find('commercial lpg'), html.lower().find('19 kg'))
            if idx > 0:
                dom_section = html[:idx]
                com_section = html[idx:]

        dom_pairs = _parse_goodreturns_table(dom_section)
        com_pairs = _parse_goodreturns_table(com_section)

        if dom_pairs:
            results["lpg_dom_mum"] = dom_pairs
            print(f"  OK lpg_dom_mum: {len(dom_pairs)} obs, latest {dom_pairs[-1]}")
        else:
            print(f"  XX lpg_dom_mum: table parse returned nothing")

        if com_pairs:
            results["lpg_com_mum"] = com_pairs
            print(f"  OK lpg_com_mum: {len(com_pairs)} obs, latest {com_pairs[-1]}")
        else:
            print(f"  XX lpg_com_mum: no commercial data")
    except Exception as e:
        print(f"  XX LPG: {e}")

    if not results:
        print("  ** goodreturns returned nothing; will use fuel-prices.json fallback.")
    return results


def merge_scraped_history(existing_pairs, scraped_pairs, rebase_date):
    """
    Merge newly scraped historical pairs into existing list.
    Scraped data wins over existing for the same date.
    Only keeps dates >= rebase_date.
    """
    merged = {d: p for d, p in existing_pairs if d >= rebase_date}
    for d, p in scraped_pairs:
        if d >= rebase_date:
            merged[d] = p
    return sorted(merged.items())


def load_manual_json(path, label):
    if not path.exists():
        print(f"[{label}] {path.name} not found.")
        return {}
    try:
        with open(path) as f:
            data = json.load(f)
        return {k: v for k, v in data.items() if not k.startswith("_") and k != "items"}
    except Exception as e:
        print(f"[{label}] parse failed: {e}")
        return {}


def merge_scraped_into_manual(manual, scraped, today_iso):
    """Append today's scraped price into manual dict if it differs from last."""
    for iid, price in scraped.items():
        if iid not in manual:
            manual[iid] = {"base_price": price, "prices": [[today_iso, price]]}
            continue
        entry = manual[iid]
        prices = entry.setdefault("prices", [])
        if not prices:
            prices.append([today_iso, price])
            entry["base_price"] = price
            continue
        last_date, last_price = prices[-1]
        if today_iso > last_date and abs(float(last_price) - float(price)) > 0.005:
            prices.append([today_iso, round(price, 2)])
            print(f"  -> recorded revision: {iid} {last_price} -> {price} on {today_iso}")
    return manual


def write_manual_back(path, manual):
    existing = {}
    if path.exists():
        with open(path) as f:
            existing = json.load(f)
    for k in list(existing.keys()):
        if not k.startswith("_"):
            existing.pop(k, None)
    existing.update(manual)
    with open(path, "w") as f:
        json.dump(existing, f, indent=2)


def base_price_from_series(pairs, rebase_date):
    if not pairs:
        return None
    pairs = sorted(pairs, key=lambda p: p[0])
    base = None
    for d, p in pairs:
        if d <= rebase_date:
            base = p
        else:
            break
    if base is None:
        base = pairs[0][1]
    return base


def trim_from(pairs, cutoff):
    return [[d, p] for d, p in pairs if d >= cutoff]


def forward_fill(pairs, all_dates):
    if not pairs:
        return []
    sparse = {d: v for d, v in pairs}
    pairs_sorted = sorted(pairs, key=lambda x: x[0])
    start_date = pairs_sorted[0][0]
    out, last = [], None
    for d in all_dates:
        if d in sparse:
            last = sparse[d]
        if last is not None and d >= start_date:
            out.append([d, last])
    return out


def compute_equal_weighted_index(components, instruments_dict, rebase_date):
    """
    Equal-weighted: each component rebased to 100 on rebase_date, then averaged.
    Result: a synthetic index starting at 100 on rebase_date.
    """
    rebased = {}
    for cid in components:
        inst = instruments_dict.get(cid)
        if not inst or not inst.get("prices"):
            print(f"  ** Fert index: missing {cid}")
            continue
        base = inst["base_price"]
        rebased[cid] = {d: (p / base * 100) for d, p in inst["prices"]}

    if not rebased:
        return []

    all_dates = sorted(set().union(*[set(s.keys()) for s in rebased.values()]))
    index_pairs = []
    for d in all_dates:
        vals = [s[d] for s in rebased.values() if d in s]
        if vals:
            index_pairs.append([d, round(sum(vals) / len(vals), 4)])
    return index_pairs


# ============================================================
# Main
# ============================================================

def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    today_iso = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%Y-%m-%d")

    yahoo_data = fetch_yahoo(FETCH_START)

    try:
        scraped = scrape_goodreturns()
    except Exception as e:
        print(f"[goodreturns] hard failure: {e}")
        scraped = {}

    fuel_manual_raw = load_manual_json(FUEL_INPUT_FILE, "fuel")

    # Merge scraped history into fuel series
    for iid, scraped_pairs in scraped.items():
        existing = []
        if iid in fuel_manual_raw and "prices" in fuel_manual_raw[iid]:
            existing = fuel_manual_raw[iid]["prices"]
        merged = merge_scraped_history(existing, scraped_pairs, FETCH_START)
        base = fuel_manual_raw.get(iid, {}).get("base_price") or (merged[0][1] if merged else None)
        fuel_manual_raw[iid] = {"base_price": base, "prices": merged}
        if merged:
            print(f"  -> fuel {iid}: {len(merged)} obs, latest {merged[-1]}")

    # Persist updated fuel-prices.json (so manual fallback stays current)
    if scraped:
        try:
            write_manual_back(FUEL_INPUT_FILE, fuel_manual_raw)
        except Exception as e:
            print(f"[fuel] couldn't persist scraped values: {e}")

    cpi_manual = load_manual_json(CPI_INPUT_FILE, "cpi")

    instruments_out = {}

    # Yahoo
    for iid, pairs in yahoo_data.items():
        pairs = trim_from(pairs, FETCH_START)
        if not pairs:
            continue
        base = base_price_from_series(pairs, REBASE_DATE)
        instruments_out[iid] = {"base_price": base, "prices": pairs}

    # Synthetic fert index
    fert_pairs = compute_equal_weighted_index(FERT_INDEX_COMPONENTS, instruments_out, REBASE_DATE)
    if fert_pairs:
        base = base_price_from_series(fert_pairs, REBASE_DATE) or 100.0
        instruments_out["fert_index"] = {"base_price": base, "prices": fert_pairs}
        print(f"  OK fert_index: {len(fert_pairs)} obs, latest {fert_pairs[-1]}")

    # Date union for forward-fill
    market_dates = sorted(set().union(*[
        {d for d, _ in v["prices"]} for v in instruments_out.values()
    ])) if instruments_out else []

    # Forward-fill fuel & CPI
    for iid, payload in fuel_manual_raw.items():
        if not isinstance(payload, dict) or "prices" not in payload:
            continue
        sparse = sorted(payload["prices"], key=lambda x: x[0])
        sparse = [p for p in sparse if p[0] >= FETCH_START]
        filled = forward_fill(sparse, market_dates)
        if filled:
            base = payload.get("base_price") or base_price_from_series(sparse, REBASE_DATE)
            instruments_out[iid] = {"base_price": base, "prices": filled}

    for iid, payload in cpi_manual.items():
        if not isinstance(payload, dict) or "prices" not in payload:
            continue
        sparse = sorted(payload["prices"], key=lambda x: x[0])
        sparse = [p for p in sparse if p[0] >= FETCH_START]
        filled = forward_fill(sparse, market_dates)
        if filled:
            base = payload.get("base_price") or base_price_from_series(sparse, REBASE_DATE)
            instruments_out[iid] = {"base_price": base, "prices": filled}

    output = {
        "metadata": {
            "speech_date": SPEECH_DATE,
            "rebase_date": REBASE_DATE,
            "rebase_note": "Last available pre-speech close (10 May was Sunday, market closed).",
            "last_updated": datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat(),
            "generated_by": "scripts/fetch.py",
            "instrument_count": len(instruments_out),
        },
        "instruments": instruments_out,
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nWrote {OUTPUT_FILE} with {len(instruments_out)} instruments")
    return 0


if __name__ == "__main__":
    sys.exit(main())
