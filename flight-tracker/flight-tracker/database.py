import sqlite3
import os
from datetime import datetime

DATABASE_PATH = os.environ.get('DATABASE_PATH', 'flight_tracker.db')


def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS routes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            origin TEXT NOT NULL,
            destination TEXT NOT NULL,
            origin_name TEXT DEFAULT '',
            destination_name TEXT DEFAULT '',
            departure_date TEXT NOT NULL,
            return_date TEXT,
            trip_type TEXT NOT NULL DEFAULT 'one-way',
            seat_class TEXT DEFAULT 'economy',
            adults INTEGER DEFAULT 1,
            alert_threshold REAL DEFAULT 5.0,
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            route_id INTEGER NOT NULL,
            price REAL NOT NULL,
            currency TEXT DEFAULT 'USD',
            airline TEXT DEFAULT '',
            duration TEXT DEFAULT '',
            stops TEXT DEFAULT '',
            departure_time TEXT DEFAULT '',
            arrival_time TEXT DEFAULT '',
            searched_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (route_id) REFERENCES routes(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            route_id INTEGER NOT NULL,
            alert_type TEXT NOT NULL,
            message TEXT NOT NULL,
            old_price REAL,
            new_price REAL,
            sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (route_id) REFERENCES routes(id) ON DELETE CASCADE
        );
    ''')

    default_settings = {
        'notification_email': '',
        'gmail_sender': '',
        'gmail_app_password': '',
        'alert_on_price_drop': 'true',
        'alert_on_good_time': 'true',
        'daily_digest': 'false',
        'search_time': '07:00',
    }
    for key, value in default_settings.items():
        cursor.execute(
            'INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)',
            (key, value)
        )

    conn.commit()
    conn.close()


def get_settings():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT key, value FROM settings')
    settings = {row['key']: row['value'] for row in cursor.fetchall()}
    conn.close()
    return settings


def update_settings(settings_dict):
    conn = get_db()
    cursor = conn.cursor()
    for key, value in settings_dict.items():
        cursor.execute(
            'INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)',
            (key, str(value), datetime.utcnow().isoformat())
        )
    conn.commit()
    conn.close()


def get_routes(active_only=True):
    conn = get_db()
    cursor = conn.cursor()
    if active_only:
        cursor.execute('SELECT * FROM routes WHERE active = 1 ORDER BY created_at DESC')
    else:
        cursor.execute('SELECT * FROM routes ORDER BY created_at DESC')
    routes = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return routes


def get_route(route_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM routes WHERE id = ?', (route_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def add_route(route_data):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO routes (name, origin, destination, origin_name, destination_name,
                            departure_date, return_date, trip_type, seat_class, adults, alert_threshold)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        route_data.get('name', f"{route_data['origin'].upper()} → {route_data['destination'].upper()}"),
        route_data['origin'].upper().strip(),
        route_data['destination'].upper().strip(),
        route_data.get('origin_name', ''),
        route_data.get('destination_name', ''),
        route_data['departure_date'],
        route_data.get('return_date'),
        route_data.get('trip_type', 'one-way'),
        route_data.get('seat_class', 'economy'),
        int(route_data.get('adults', 1)),
        float(route_data.get('alert_threshold', 5.0)),
    ))
    route_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return route_id


def delete_route(route_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM routes WHERE id = ?', (route_id,))
    conn.commit()
    conn.close()


def add_price_record(route_id, price_data):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO price_history (route_id, price, currency, airline, duration, stops,
                                   departure_time, arrival_time, searched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        route_id,
        float(price_data['price']),
        price_data.get('currency', 'USD'),
        price_data.get('airline', ''),
        price_data.get('duration', ''),
        price_data.get('stops', ''),
        price_data.get('departure_time', ''),
        price_data.get('arrival_time', ''),
        datetime.utcnow().isoformat(),
    ))
    conn.commit()
    conn.close()


def get_price_history(route_id, days=90):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM price_history
        WHERE route_id = ?
        ORDER BY searched_at ASC
        LIMIT ?
    ''', (route_id, days))
    history = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return history


def add_alert(route_id, alert_type, message, old_price=None, new_price=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO alerts (route_id, alert_type, message, old_price, new_price)
        VALUES (?, ?, ?, ?, ?)
    ''', (route_id, alert_type, message, old_price, new_price))
    conn.commit()
    conn.close()


def get_recent_alerts(limit=20):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT a.*, r.name as route_name, r.origin, r.destination
        FROM alerts a
        JOIN routes r ON a.route_id = r.id
        ORDER BY a.sent_at DESC
        LIMIT ?
    ''', (limit,))
    alerts = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return alerts
