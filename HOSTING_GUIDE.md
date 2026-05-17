# Hosting Guide — Beginner-friendly, free, auto-updating

This guide walks you through hosting your Sapta Sankalp tracker on
**GitHub Pages** with **GitHub Actions** as the daily auto-updater.
Everything is free. You will not need to install anything on your
computer — all steps are done in a browser.

**Time required:** about 20 minutes the first time. Future updates
happen automatically.

---

## Step 1 — Create a GitHub account (skip if you have one)

1. Open https://github.com/signup in a new tab.
2. Use any email address. Pick any username — it will appear in your
   site URL, so pick something you're comfortable with (e.g. your
   first name, or anything neutral). You can keep it private.
3. Verify the email when prompted.

---

## Step 2 — Create a new repository

A "repository" is just a folder on GitHub.

1. Once logged in, click the **+** icon top-right → **New repository**.
2. **Repository name:** `sapta-sankalp` (or whatever name you chose).
3. **Description:** _Tracking publicly available market indicators related
   to the seven appeals._
4. Select **Public** (Pages requires public for free accounts).
5. Check **Add a README file** — this initializes the repo so we can
   add files easily.
6. Click **Create repository**.

You'll land on the empty repo page.

---

## Step 3 — Upload the files

You have a folder on your computer with the eight files I prepared.
We'll upload them all at once.

1. On the repo page, click **Add file → Upload files**.
2. Drag the **entire folder structure** I gave you into the upload
   area. Make sure the folder structure is preserved:

   ```
   index.html
   README.md
   HOSTING_GUIDE.md
   requirements.txt
   data/
     prices.json
     fuel-prices.json
   scripts/
     fetch.py
   .github/
     workflows/
       update.yml
   ```

3. If drag-drop doesn't preserve folders in your browser, click
   **choose your files** and select all files at once — GitHub
   will keep the paths if they were inside the right folders.
4. At the bottom, write a commit message like _"initial upload"_
   and click **Commit changes**.

> If GitHub gives you trouble preserving the folder structure via the
> browser upload, the alternative is to install **GitHub Desktop**
> (https://desktop.github.com — free GUI tool, no command line needed),
> clone the empty repo, copy your folder contents in, and click
> "Commit to main" then "Push origin." This is more reliable for
> nested folders.

---

## Step 4 — Allow GitHub Actions to write to your repo

The bot needs permission to commit the daily data updates back to
your repo. This is a one-click setting.

1. In your repo, click **Settings** (top tabs).
2. Left sidebar → **Actions → General**.
3. Scroll to **Workflow permissions** near the bottom.
4. Select **Read and write permissions** (instead of "Read repository
   contents permission").
5. Click **Save**.

---

## Step 5 — Enable GitHub Pages (the actual website hosting)

1. Still in **Settings**, left sidebar → **Pages**.
2. Under **Build and deployment → Source**, select **Deploy from a branch**.
3. Under **Branch**, select **main** and **/ (root)** as the folder.
4. Click **Save**.
5. Wait 1–2 minutes. The page will refresh and show:

   > _Your site is live at https://**\<your-username\>**.github.io/sapta-sankalp/_

6. Open that URL. You should see the tracker page. If it shows the
   site but with a red error box about data, that's expected on
   first load — proceed to Step 6.

---

## Step 6 — Run the data fetcher once manually

The schedule will pick up automatically tomorrow, but let's run it
once now so you have fresh data right away.

1. In your repo, click the **Actions** tab.
2. You may see a banner saying "Workflows aren't enabled" — click
   **I understand my workflows, go ahead and enable them**.
3. In the left sidebar, click **Daily price update**.
4. On the right, click **Run workflow → Run workflow** (green button).
5. Wait about 60–90 seconds. The yellow circle becomes a green check
   when it's done.
6. Refresh your live site. You should now see real data points filling
   in from May 8 onwards.

---

## Step 7 — Done. What happens from here

- Every day at **17:00 IST (11:30 UTC)**, the workflow runs automatically,
  pulls fresh closing prices, and updates `data/prices.json`.
- GitHub Pages picks up the change within a minute or two.
- Your site reflects the latest data on every page load.

You don't have to do anything else for the daily updates.

---

## Updating fuel prices when they change

Petrol, diesel, and LPG prices revise infrequently. When a revision
is announced (you'll see it in news or on iocl.com/petrol-diesel-price):

1. In your repo, open `data/fuel-prices.json`.
2. Click the pencil ✏️ icon (top-right of the file view) to edit.
3. Find the relevant series (e.g. `petrol_del` for Delhi petrol).
4. Add a new entry to the `prices` array:

   ```json
   "prices": [
     ["2026-05-08", 96.72],
     ["2026-06-15", 97.20]    <-- new row
   ]
   ```

5. Scroll down, write a commit message like _"fuel update June 15"_,
   click **Commit changes**.
6. The next daily fetcher run will pick it up automatically.

If you want it to appear immediately, manually run the workflow as
in Step 6.

---

## Customizing the site

- **Change the site name from "Sapta Sankalp" to whatever you picked:**
  open `index.html`, search for `Sapta Sankalp`, replace all occurrences,
  commit. The page title and header both update.
- **Change colors / fonts:** the CSS variables at the top of `index.html`
  (`--bg`, `--accent`, etc.) control the palette.
- **Add or remove instruments:** edit `INSTRUMENT_META` in `index.html`
  AND `YAHOO_INSTRUMENTS` in `scripts/fetch.py`. Both must match.

---

## Troubleshooting

**The site loads but shows "Data not loaded yet".**
The fetcher hasn't run yet, or it failed. Go to **Actions** tab in
your repo, click the latest run, and read the log. Common fixes:
re-run the workflow from Step 6.

**Workflow failed with "Permission denied to push".**
You skipped Step 4. Go back and enable read/write workflow permissions.

**Workflow failed with "ticker not found" for one symbol.**
Yahoo occasionally renames or delists tickers. Open the log to see
which one. Edit `scripts/fetch.py`, update the ticker, commit. The
site will skip missing series gracefully.

**Page shows "Chart.js failed to load."**
The CDN is blocked on your network or had a brief outage. Reload
the page; if the issue persists, the CDN URL in `index.html` can
be swapped to a different provider (jsDelivr → unpkg → cdnjs).

---

## Optional: connect a custom domain

If you later buy a domain like `saptasankalp.in`, GitHub Pages
supports it for free:

1. Settings → Pages → **Custom domain** → enter your domain.
2. With your domain registrar, add a CNAME record pointing to
   `<your-username>.github.io`.
3. Wait for DNS propagation (a few hours), then enable
   **Enforce HTTPS**.

This is purely optional; the free `.github.io` URL works perfectly fine.
