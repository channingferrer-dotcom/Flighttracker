# ✈️ Flight Price Tracker

A web app that searches Google Flights daily at 7 am ET, tracks price history, and emails you when prices drop or it's a good time to book.

---

## Features

- Track 1–10 flight routes (one-way, round-trip)
- Daily automated search at 7 am ET (cloud scheduler — no computer needed)
- Price history charts for each route
- **"Good time to buy" engine** powered by data from Expedia 2025 Air Hacks, CheapAir, and Google Flights research
- Email alerts via Gmail when prices drop or booking window opens
- Optional daily digest email

---

## Deploy to Railway (10-minute setup)

### Step 1 — Create a GitHub repository

1. Go to [github.com](https://github.com) and sign up / log in (free)
2. Click **"New repository"**, name it `flight-tracker`, set it to **Private**, click **Create**
3. Upload the contents of this folder into the repo (drag-and-drop or use the GitHub web editor)

### Step 2 — Create a Railway account

1. Go to [railway.app](https://railway.app) and sign up with your GitHub account (free)
2. Click **"New Project"** → **"Deploy from GitHub repo"**
3. Select your `flight-tracker` repository
4. Railway will auto-detect Python and start deploying

### Step 3 — Add a persistent volume (for the database)

1. In your Railway project, click your service → **"Volumes"** tab → **"Add Volume"**
2. Set **Mount Path** to `/data`
3. Go to **Variables** tab and add:
   ```
   DATABASE_PATH = /data/flight_tracker.db
   ```

### Step 4 — Configure Gmail (one-time)

**Generate a Gmail App Password:**
1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Sign in → Select "Mail" and "Other (custom name)" → type "Flight Tracker" → click Generate
3. Copy the 16-character password shown (you'll paste this into the app settings)

> **Note:** You need 2-Step Verification enabled on your Google account for App Passwords to work. Enable it at [myaccount.google.com/security](https://myaccount.google.com/security).

### Step 5 — Open the app and configure

1. In Railway, click your service → **"Settings"** → copy the public URL (e.g. `https://flight-tracker-abc123.railway.app`)
2. Open that URL in your browser
3. Click **⚙️ Settings** in the top right
4. Enter:
   - **Send Alerts To** — your personal email address
   - **Gmail Sender Address** — the Gmail account you generated the App Password for
   - **Gmail App Password** — the 16-character password from Step 4
5. Click **"Send Test Email"** to confirm it's working
6. Save settings

### Step 6 — Add your first route

1. Click **"+ Add Route"**
2. Enter origin and destination as 3-letter IATA airport codes (e.g. `JFK` → `LAX`)
3. Set your departure date, trip type, and alert threshold
4. Click **"Add Route"** — the app will run an immediate search

---

## IATA Airport Code Examples

| City | Code |
|------|------|
| New York (JFK) | JFK |
| New York (Newark) | EWR |
| Los Angeles | LAX |
| Miami | MIA |
| Chicago | ORD |
| San Francisco | SFO |
| London Heathrow | LHR |
| Paris CDG | CDG |
| Cancun | CUN |
| London Gatwick | LGW |

---

## How the "Good Time to Buy" engine works

The recommendation engine combines live price trends with research from:

- **Expedia 2025 Air Hacks Report** — Book on Sundays (save 17%); domestic sweet spot is 1–3 months out; Friday departures are cheapest
- **CheapAir 2024 Annual Airfare Study** — Optimal domestic booking: ~42 days before departure; prices fluctuate ~49 times per fare
- **Google Flights data** — Domestic lowest prices at ~39 days out; international at 49+ days; layovers save ~22%

**Status meanings:**
| Status | Meaning |
|--------|---------|
| ✅ Good Time to Buy | In the optimal booking window AND price is at/below recent average |
| 📈 Buy Soon | In the window but prices are rising — act soon |
| ⏳ Wait — Prices Falling | Price trending down and you have runway — hold off a few days |
| 👀 Monitor Closely | In the window but price above average — watch for a dip |
| 🔍 Too Early | Not yet in the optimal booking window |
| ⚡ Book Immediately | Inside 14 days — prices spike fast, book now |

---

## Local development (optional)

If you want to run the app locally for testing:

```bash
# Install Python 3.10+ from python.org if needed
pip install -r requirements.txt
python app.py
# Open http://localhost:5000
```

---

## Troubleshooting

**"Search failed" error on a route**
The `fast-flights` scraper uses Google Flights' internal API. Occasional failures are normal — the daily scheduler will retry automatically. If it fails consistently, Google may have changed their format; check for a newer version of `fast-flights` in `requirements.txt`.

**Not receiving emails**
1. Confirm 2-Step Verification is enabled on your Google account
2. Make sure you used an App Password (16 characters, no spaces) — not your regular Gmail password
3. Click "Send Test Email" in Settings to diagnose

**Database resets after redeploy**
Make sure you added the Railway volume at `/data` and set `DATABASE_PATH=/data/flight_tracker.db` in environment variables.
