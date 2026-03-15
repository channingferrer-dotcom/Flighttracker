import os
import logging
from flask import Flask, render_template, jsonify, request
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from database import (
    init_db, get_routes, get_route, add_route, delete_route,
    add_price_record, get_price_history, get_settings, update_settings,
    add_alert, get_recent_alerts,
)
from scraper import search_flights
from analyzer import get_recommendation, get_price_summary
from notifier import (
    send_price_drop_alert, send_good_time_alert,
    send_daily_digest, send_test_email,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-8s  %(name)s — %(message)s',
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
scheduler = BackgroundScheduler(timezone=pytz.utc)


# ── Core search logic ─────────────────────────────────────────────────────────

def _process_route(route, settings):
    """
    Run a search for one route, persist the result, and fire any alerts.
    Returns a dict ready for the daily digest, or None if the search failed.
    """
    result = search_flights(route)
    if not result:
        logger.warning(f'No result for route {route["id"]}: {route["origin"]} → {route["destination"]}')
        return None

    add_price_record(route['id'], result)
    history = get_price_history(route['id'])
    summary = get_price_summary(history)
    rec = get_recommendation(route, history)

    # ── Price-drop alert ──
    if len(history) >= 2 and settings.get('alert_on_price_drop') == 'true':
        prev_price = history[-2]['price']
        curr_price = result['price']
        threshold = float(route.get('alert_threshold') or 5.0)
        pct_drop = (prev_price - curr_price) / prev_price * 100 if prev_price else 0

        if pct_drop >= threshold:
            msg = f'Price dropped {pct_drop:.1f}% to ${curr_price:,.0f}'
            add_alert(route['id'], 'price_drop', msg, prev_price, curr_price)
            send_price_drop_alert(settings, route, prev_price, curr_price, rec)
            logger.info(f'Price-drop alert sent for route {route["id"]}')

    # ── "Good time to buy" alert ──
    if (
        settings.get('alert_on_good_time') == 'true'
        and rec['status'] == 'GOOD_TIME'
        and len(history) >= 3   # avoid alerting on the very first data points
    ):
        msg = f'Good time to buy: {rec["reason"]}'
        add_alert(route['id'], 'good_time', msg)
        send_good_time_alert(settings, route, result['price'], rec)
        logger.info(f'Good-time alert sent for route {route["id"]}')

    return {'route': route, 'summary': summary, 'recommendation': rec}


def run_daily_search():
    """Run the daily flight search for every active route."""
    logger.info('── Daily search starting ──')
    routes = get_routes(active_only=True)
    settings = get_settings()
    results = []

    for route in routes:
        rd = _process_route(route, settings)
        if rd:
            results.append(rd)

    # Daily digest email
    if settings.get('daily_digest') == 'true' and results:
        send_daily_digest(settings, results)

    logger.info(f'── Daily search done: {len(results)}/{len(routes)} routes OK ──')


# ── Scheduler helpers ─────────────────────────────────────────────────────────

def reschedule_job(time_str='07:00'):
    try:
        hour, minute = map(int, time_str.split(':'))
        et = pytz.timezone('US/Eastern')
        scheduler.add_job(
            run_daily_search,
            CronTrigger(hour=hour, minute=minute, timezone=et),
            id='daily_search',
            replace_existing=True,
            name='Daily Flight Search',
        )
        logger.info(f'Daily search scheduled at {time_str} ET')
    except Exception as e:
        logger.error(f'Failed to schedule job: {e}')


# ── Flask routes ──────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/routes', methods=['GET'])
def api_get_routes():
    routes = get_routes(active_only=False)
    out = []
    for route in routes:
        history = get_price_history(route['id'])
        out.append({
            **route,
            'summary': get_price_summary(history),
            'recommendation': get_recommendation(route, history),
        })
    return jsonify(out)


@app.route('/api/routes', methods=['POST'])
def api_add_route():
    data = request.get_json(force=True)
    required = ['origin', 'destination', 'departure_date', 'trip_type']
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({'error': f'Missing fields: {", ".join(missing)}'}), 400

    route_id = add_route(data)
    return jsonify({'id': route_id, 'message': 'Route added'}), 201


@app.route('/api/routes/<int:route_id>', methods=['DELETE'])
def api_delete_route(route_id):
    delete_route(route_id)
    return jsonify({'message': 'Route deleted'})


@app.route('/api/routes/<int:route_id>/search', methods=['POST'])
def api_search_route(route_id):
    route = get_route(route_id)
    if not route:
        return jsonify({'error': 'Route not found'}), 404

    settings = get_settings()
    rd = _process_route(route, settings)
    if rd:
        return jsonify({'success': True, **rd})
    return jsonify({'error': 'Search failed — scraper may be temporarily unavailable.'}), 503


@app.route('/api/routes/<int:route_id>/history', methods=['GET'])
def api_get_history(route_id):
    history = get_price_history(route_id, days=90)
    return jsonify(history)


@app.route('/api/search-all', methods=['POST'])
def api_search_all():
    run_daily_search()
    return jsonify({'message': 'Search complete for all routes'})


@app.route('/api/settings', methods=['GET'])
def api_get_settings():
    s = get_settings()
    safe = {k: v for k, v in s.items() if k != 'gmail_app_password'}
    safe['gmail_configured'] = bool(s.get('gmail_app_password'))
    return jsonify(safe)


@app.route('/api/settings', methods=['POST'])
def api_update_settings():
    data = request.get_json(force=True)
    update_settings(data)
    if 'search_time' in data:
        reschedule_job(data['search_time'])
    return jsonify({'message': 'Settings saved'})


@app.route('/api/settings/test-email', methods=['POST'])
def api_test_email():
    ok = send_test_email(get_settings())
    if ok:
        return jsonify({'success': True, 'message': 'Test email sent!'})
    return jsonify({'success': False, 'message': 'Failed — check your Gmail settings.'}), 500


@app.route('/api/alerts', methods=['GET'])
def api_get_alerts():
    return jsonify(get_recent_alerts(limit=20))


@app.route('/api/next-search', methods=['GET'])
def api_next_search():
    job = scheduler.get_job('daily_search')
    if job and job.next_run_time:
        return jsonify({'next_run': job.next_run_time.isoformat()})
    return jsonify({'next_run': None})


# ── Startup ───────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    settings = get_settings()
    scheduler.start()
    reschedule_job(settings.get('search_time', '07:00'))
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
