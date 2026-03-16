"""
Flight price analysis and buy-recommendation engine.

Research sources baked into this module:
  - Expedia 2025 Air Hacks Report
      • Book on Sundays (save up to 17% vs Monday)
      • Domestic: book 1–3 months out, save ~25%
      • International: 18–29 days out saves up to 17% (short haul); longer hauls need more lead time
      • Cheapest months: August (domestic); January (international)
  - CheapAir 2024 Annual Airfare Study
      • Domestic sweet spot: ~42 days out (range 2.5–3 months)
      • Prices change ~49 times per fare; average swing ~$43
  - Google Flights data
      • Domestic lowest at ~39 days out (range: 23–51 days)
      • International lowest at 49+ days
      • Layovers save ~22%
  - General industry data
      • Last-minute spike: prices ~double in final 14 days
      • Midweek departures (Tue/Wed/Sat domestic; Wed/Thu international) 13–15% cheaper
"""

from datetime import date, datetime
from statistics import mean

# ── Booking window constants (days before departure) ──────────────────────────
DOMESTIC_OPT_MIN = 21       # below this = last-minute danger zone
DOMESTIC_OPT_MAX = 90
DOMESTIC_SWEET_SPOT = 42    # CheapAir + Google consensus

INTL_OPT_MIN = 21
INTL_OPT_MAX = 180
INTL_SWEET_SPOT = 70        # conservative midpoint of 49–90 days

LAST_MINUTE_DAYS = 14       # prices spike hard inside 2 weeks

# ── Price change thresholds ───────────────────────────────────────────────────
SIGNIFICANT_DROP_PCT = 5.0
GREAT_DEAL_PCT = 10.0
SIGNIFICANT_RISE_PCT = 5.0

# ── Known international IATA codes (partial list for heuristic) ───────────────
_INTL_CODES = {
    'LHR', 'LGW', 'STN', 'CDG', 'ORY', 'FRA', 'MUC', 'AMS', 'BRU',
    'ZRH', 'GVA', 'FCO', 'MXP', 'MAD', 'BCN', 'LIS', 'ATH', 'IST',
    'DXB', 'AUH', 'DOH', 'NRT', 'HND', 'ICN', 'PEK', 'PVG', 'CAN',
    'HKG', 'SIN', 'KUL', 'BKK', 'CGK', 'MNL', 'SYD', 'MEL', 'BOM',
    'DEL', 'YYZ', 'YVR', 'YUL', 'MEX', 'CUN', 'GRU', 'EZE', 'BOG',
    'SCL', 'LIM', 'GIG', 'NBO', 'JNB', 'CAI', 'CPH', 'OSL', 'ARN',
    'HEL', 'DUB', 'TLV', 'LAG',
}


def is_international(origin: str, destination: str) -> bool:
    o, d = origin.upper().strip(), destination.upper().strip()
    return o in _INTL_CODES or d in _INTL_CODES


def _parse_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def _days_to_departure(departure_date_str):
    dep = _parse_date(departure_date_str)
    if dep is None:
        return None
    return (dep - date.today()).days


def _price_trend(prices):
    """
    Returns (trend_label, pct_vs_yesterday, pct_vs_7d_avg).
    trend_label: 'dropping_fast' | 'dropping' | 'stable' | 'rising' | 'rising_fast'
    """
    if len(prices) < 2:
        return 'stable', 0.0, 0.0

    current = prices[-1]
    prev = prices[-2]
    pct_1d = round((current - prev) / prev * 100, 1) if prev else 0.0

    week = prices[-8:-1] if len(prices) >= 8 else prices[:-1]
    avg_7d = mean(week) if week else prev
    pct_7d = round((current - avg_7d) / avg_7d * 100, 1) if avg_7d else 0.0

    if pct_7d <= -GREAT_DEAL_PCT:
        label = 'dropping_fast'
    elif pct_7d <= -SIGNIFICANT_DROP_PCT:
        label = 'dropping'
    elif pct_7d >= GREAT_DEAL_PCT:
        label = 'rising_fast'
    elif pct_7d >= SIGNIFICANT_RISE_PCT:
        label = 'rising'
    else:
        label = 'stable'

    return label, pct_1d, pct_7d


def _departure_day_tip(departure_date_str, intl):
    dep = _parse_date(departure_date_str)
    if dep is None:
        return None
    day = dep.strftime('%A')
    if intl and day not in ('Wednesday', 'Thursday'):
        return f"Your flight departs on {day}. Wed/Thu are typically 15% cheaper for international."
    if not intl and day not in ('Tuesday', 'Wednesday', 'Saturday'):
        return f"Your flight departs on {day}. Tue/Wed/Sat departures are ~13% cheaper domestically."
    return None


def get_price_summary(price_history):
    """Return a dict of key price statistics for display."""
    if not price_history:
        return {}
    prices = [h['price'] for h in price_history if h.get('price')]
    if not prices:
        return {}

    current = prices[-1]
    prev = prices[-2] if len(prices) > 1 else current
    avg_7d = mean(prices[-7:]) if len(prices) >= 7 else mean(prices)
    avg_30d = mean(prices[-30:]) if len(prices) >= 30 else mean(prices)

    return {
        'current': round(current, 2),
        'previous': round(prev, 2),
        'change_1d': round(current - prev, 2),
        'change_1d_pct': round((current - prev) / prev * 100, 1) if prev else 0,
        'avg_7d': round(avg_7d, 2),
        'avg_30d': round(avg_30d, 2),
        'all_time_low': round(min(prices), 2),
        'all_time_high': round(max(prices), 2),
        'data_points': len(prices),
    }


def get_recommendation(route, price_history):
    """
    Generate a buy recommendation.

    Returns a dict:
      status   : 'BUY_NOW' | 'GOOD_TIME' | 'WAIT' | 'MONITOR' | 'MONITORING'
      color    : 'red' | 'green' | 'orange' | 'yellow' | 'blue'
      headline : short phrase for display
      reason   : one-sentence explanation
      tips     : list[str] of actionable tips (max 3)
    """
    if not price_history:
        return {
            'status': 'MONITORING',
            'color': 'blue',
            'headline': 'Tracking Started',
            'reason': 'First search running. Check back after a few days as more data accumulates.',
            'tips': ['Prices are tracked daily at 7 am ET.'],
        }

    prices = [h['price'] for h in price_history if h.get('price')]
    if not prices:
        return {
            'status': 'MONITORING',
            'color': 'blue',
            'headline': 'No Prices Yet',
            'reason': 'The scraper has not returned valid prices for this route yet.',
            'tips': ['Try clicking "Search Now" to trigger a manual search.'],
        }

    current = prices[-1]
    avg_7d = mean(prices[-7:]) if len(prices) >= 7 else mean(prices)
    avg_30d = mean(prices[-30:]) if len(prices) >= 30 else mean(prices)
    all_time_low = min(prices)

    trend, pct_1d, pct_7d = _price_trend(prices)
    days = _days_to_departure(route.get('departure_date'))
    intl = is_international(route.get('origin', ''), route.get('destination', ''))

    opt_min = INTL_OPT_MIN if intl else DOMESTIC_OPT_MIN
    opt_max = INTL_OPT_MAX if intl else DOMESTIC_OPT_MAX
    sweet = INTL_SWEET_SPOT if intl else DOMESTIC_SWEET_SPOT
    label = 'international' if intl else 'domestic'

    tips = []

    # ── Collect context-aware tips ────────────────────────────────────────────
    day_tip = _departure_day_tip(route.get('departure_date'), intl)
    if day_tip:
        tips.append(day_tip)
    tips.append('Flights with 1 stop are ~22% cheaper than nonstop (Google Flights data).')
    tips.append('Book on a Sunday — historically the cheapest day to purchase (up to 17% savings per Expedia).')

    def _trim(t):
        return t[:3]

    # ── Decision tree ─────────────────────────────────────────────────────────

    # 1. Departure date unknown — can still give price-trend advice
    if days is None:
        if trend in ('dropping', 'dropping_fast'):
            return {
                'status': 'WAIT',
                'color': 'orange',
                'headline': '⏳ Prices Dropping — Wait',
                'reason': f'Price is down {abs(pct_7d):.1f}% over the past 7 days. Add a departure date for full analysis.',
                'tips': _trim(tips),
            }
        return {
            'status': 'MONITOR',
            'color': 'blue',
            'headline': '🔍 Add Departure Date',
            'reason': 'Add a departure date to get a personalised buy recommendation.',
            'tips': _trim(tips),
        }

    # 2. Past travel date
    if days < 0:
        return {
            'status': 'MONITOR',
            'color': 'blue',
            'headline': '🗓️ Trip Date Passed',
            'reason': 'The departure date for this route has already passed.',
            'tips': ['Update the route with a new departure date.'],
        }

    # 3. Last-minute — book immediately
    if days < LAST_MINUTE_DAYS:
        return {
            'status': 'BUY_NOW',
            'color': 'red',
            'headline': '⚡ Book Immediately',
            'reason': (
                f'Only {days} day{"s" if days != 1 else ""} to departure — '
                'prices typically double inside the 2-week window. Don\'t wait.'
            ),
            'tips': [
                'Book today to avoid further price spikes.',
                'Check nearby airports for last-minute savings.',
                'Flexible ±1 day may still uncover a better price.',
            ],
        }

    in_window = opt_min <= days <= opt_max
    has_history = len(prices) >= 3  # need at least 3 points for reliable trends

    # 4. In window + price at or below 7-day average → great time
    below_avg = current <= avg_7d * 0.97          # 3%+ below 7-day avg
    near_low = current <= all_time_low * 1.05     # within 5% of tracked low
    if in_window and (below_avg or near_low) and has_history:
        pct_below = round((avg_7d - current) / avg_7d * 100, 1)
        return {
            'status': 'GOOD_TIME',
            'color': 'green',
            'headline': '✅ Good Time to Buy',
            'reason': (
                f'You\'re {days} days out (inside the optimal {opt_min}–{opt_max}-day window) '
                f'and the price is {pct_below}% below the 7-day average.'
            ),
            'tips': _trim(tips),
        }

    # 5. Price dropping fast + enough runway to wait
    if trend in ('dropping', 'dropping_fast') and days > opt_min + 7:
        return {
            'status': 'WAIT',
            'color': 'orange',
            'headline': '⏳ Wait — Prices Falling',
            'reason': (
                f'Price has fallen {abs(pct_7d):.1f}% over the past 7 days. '
                f'You have {days} days — enough runway to wait for a better price.'
            ),
            'tips': [
                f'Target price: ~${round(current * 0.92):,} (8% lower).',
                'Check back in 3–5 days to see if the trend continues.',
                f'Don\'t wait past {opt_min} days before departure — prices spike fast.',
            ],
        }

    # 6. In window + rising prices → act soon
    if in_window and trend in ('rising', 'rising_fast'):
        return {
            'status': 'BUY_NOW',
            'color': 'red',
            'headline': '📈 Buy Soon — Prices Rising',
            'reason': (
                f'Price is up {abs(pct_7d):.1f}% over the past 7 days '
                f'and you\'re in the optimal booking window ({days} days out).'
            ),
            'tips': _trim(tips),
        }

    # 7. In window but price above average — keep watching
    if in_window and not below_avg:
        return {
            'status': 'MONITOR',
            'color': 'yellow',
            'headline': '👀 In Window — Watch for a Dip',
            'reason': (
                f'You\'re {days} days out (optimal window) but the price is '
                f'{round((current - avg_7d) / avg_7d * 100, 1):.1f}% above the 7-day average. '
                'Wait for a small pullback if the calendar allows.'
            ),
            'tips': [
                f'A 5%+ drop would be a strong buying signal.',
                f'The research-backed sweet spot for {label} flights is ~{sweet} days out.',
                f'Don\'t wait past {opt_min} days before departure.',
            ],
        }

    # 8. Too early — not yet in window
    if days > opt_max:
        days_until_window = days - opt_max
        return {
            'status': 'MONITOR',
            'color': 'blue',
            'headline': '🔍 Too Early — Keep Watching',
            'reason': (
                f'You have {days} days to go — the optimal booking window opens '
                f'in ~{days_until_window} days ({opt_max} days before departure).'
            ),
            'tips': [
                f'Best booking window for {label} flights: {opt_min}–{opt_max} days out.',
                f'Historically, ~{sweet} days out is the sweet spot.',
                'We\'ll alert you when prices drop or the window opens.',
            ],
        }

    # 9. Catch-all
    return {
        'status': 'MONITOR',
        'color': 'blue',
        'headline': '🔍 Monitoring',
        'reason': f'Tracking this route. Current price: ${current:,.0f}. {days} days to departure.',
        'tips': _trim(tips),
    }
