import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Colour palette for recommendation statuses ────────────────────────────────
_STATUS_COLORS = {
    'green':  {'bg': '#f0fdf4', 'border': '#86efac', 'text': '#16a34a'},
    'yellow': {'bg': '#fefce8', 'border': '#fde047', 'text': '#ca8a04'},
    'orange': {'bg': '#fff7ed', 'border': '#fdba74', 'text': '#ea580c'},
    'red':    {'bg': '#fef2f2', 'border': '#fca5a5', 'text': '#dc2626'},
    'blue':   {'bg': '#eff6ff', 'border': '#93c5fd', 'text': '#2563eb'},
}


def _colors(color_key):
    return _STATUS_COLORS.get(color_key, _STATUS_COLORS['blue'])


def _send(settings, subject, html_body):
    """Core send function — returns True on success."""
    sender = settings.get('gmail_sender', '').strip()
    password = settings.get('gmail_app_password', '').strip()
    recipient = settings.get('notification_email', '').strip()

    if not all([sender, password, recipient]):
        logger.warning('Email not fully configured — skipping notification.')
        return False

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f'Flight Tracker <{sender}>'
        msg['To'] = recipient
        msg.attach(MIMEText(html_body, 'html'))

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender, password)
            server.sendmail(sender, recipient, msg.as_string())

        logger.info(f'Email sent → {recipient}: {subject}')
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error('Gmail authentication failed. Check your App Password.')
        return False
    except Exception as e:
        logger.error(f'Failed to send email: {e}', exc_info=True)
        return False


# ── Email templates ───────────────────────────────────────────────────────────

_BASE_HEADER = '''
<div style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);
            border-radius:12px;padding:24px;margin-bottom:20px;color:#fff;">
  <h1 style="margin:0 0 6px 0;font-size:22px;">✈️ {title}</h1>
  <p style="margin:0;opacity:.85;font-size:14px;">{subtitle}</p>
</div>
'''

_BASE_FOOTER = '''
<p style="color:#9ca3af;font-size:11px;text-align:center;margin-top:28px;border-top:1px solid #e5e7eb;padding-top:16px;">
  Sent by your Flight Tracker &nbsp;·&nbsp; Prices from Google Flights
</p>
'''

_WRAP_OPEN = '''<html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  max-width:600px;margin:0 auto;padding:20px;color:#1a1a1a;">'''
_WRAP_CLOSE = '</body></html>'


def _rec_block(rec):
    c = _colors(rec.get('color', 'blue'))
    tips_html = ''
    if rec.get('tips'):
        items = ''.join(f'<li style="padding:3px 0;font-size:13px;">{t}</li>' for t in rec['tips'])
        tips_html = f'''
        <div style="background:#f9fafb;border-radius:8px;padding:14px;margin-top:12px;">
          <p style="margin:0 0 8px 0;font-size:11px;font-weight:600;
                    text-transform:uppercase;letter-spacing:.05em;color:#6b7280;">💡 Tips</p>
          <ul style="margin:0;padding-left:18px;">{items}</ul>
        </div>'''

    return f'''
    <div style="background:{c['bg']};border:1.5px solid {c['border']};
                border-radius:10px;padding:16px;margin-bottom:16px;">
      <p style="margin:0 0 6px 0;font-weight:700;color:{c['text']};font-size:16px;">
        {rec.get('headline', '')}
      </p>
      <p style="margin:0;font-size:14px;color:#374151;">{rec.get('reason', '')}</p>
      {tips_html}
    </div>'''


def _route_detail_table(route):
    rows = [
        ('Route', f"{route.get('origin', '')} → {route.get('destination', '')}"),
        ('Departure', route.get('departure_date', '—')),
        ('Return', route.get('return_date') or '—'),
        ('Type', (route.get('trip_type') or 'one-way').replace('-', ' ').title()),
        ('Class', (route.get('seat_class') or 'economy').title()),
    ]
    tds = ''.join(
        f'<tr><td style="padding:5px 0;color:#6b7280;font-size:13px;width:110px;">{k}</td>'
        f'<td style="padding:5px 0;font-weight:600;font-size:13px;">{v}</td></tr>'
        for k, v in rows if v and v != '—' or k == 'Departure'
    )
    return f'''
    <div style="background:#f9fafb;border-radius:10px;padding:16px;margin-bottom:16px;">
      <p style="margin:0 0 10px 0;font-size:11px;font-weight:600;
                text-transform:uppercase;letter-spacing:.05em;color:#6b7280;">Route Details</p>
      <table style="width:100%;border-collapse:collapse;">{tds}</table>
    </div>'''


# ── Public API ────────────────────────────────────────────────────────────────

def send_price_drop_alert(settings, route, old_price, new_price, recommendation):
    """Send an alert when a significant price drop is detected."""
    pct = round((old_price - new_price) / old_price * 100, 1)
    route_name = route.get('name') or f"{route['origin']} → {route['destination']}"
    subject = f'✈️ Price Drop: {route_name} — now ${new_price:,.0f} (↓{pct}%)'

    html = _WRAP_OPEN
    html += _BASE_HEADER.format(title='Price Drop Alert', subtitle=route_name)
    html += f'''
    <div style="background:#f0fdf4;border:2px solid #86efac;border-radius:10px;
                padding:20px;margin-bottom:16px;text-align:center;">
      <p style="margin:0 0 6px 0;font-size:11px;font-weight:600;
                text-transform:uppercase;letter-spacing:.05em;color:#16a34a;">Price Drop Detected</p>
      <div style="display:flex;justify-content:center;align-items:center;gap:16px;flex-wrap:wrap;">
        <span style="color:#9ca3af;text-decoration:line-through;font-size:22px;">
          ${old_price:,.0f}
        </span>
        <span style="color:#16a34a;font-size:34px;font-weight:700;">${new_price:,.0f}</span>
        <span style="background:#16a34a;color:#fff;padding:4px 14px;
                     border-radius:20px;font-weight:700;font-size:14px;">↓{pct}%</span>
      </div>
    </div>'''
    html += _rec_block(recommendation)
    html += _route_detail_table(route)
    html += _BASE_FOOTER
    html += _WRAP_CLOSE

    return _send(settings, subject, html)


def send_good_time_alert(settings, route, current_price, recommendation):
    """Send an alert when the analyzer says it's a good time to buy."""
    route_name = route.get('name') or f"{route['origin']} → {route['destination']}"
    subject = f'✈️ Good Time to Buy: {route_name} — ${current_price:,.0f}'

    html = _WRAP_OPEN
    html += _BASE_HEADER.format(title='Good Time to Buy', subtitle=route_name)
    html += f'''
    <div style="background:#f0fdf4;border:2px solid #86efac;border-radius:10px;
                padding:20px;margin-bottom:16px;text-align:center;">
      <p style="margin:0 0 4px 0;font-size:11px;font-weight:600;
                text-transform:uppercase;letter-spacing:.05em;color:#16a34a;">Current Best Price</p>
      <span style="color:#16a34a;font-size:40px;font-weight:700;">${current_price:,.0f}</span>
    </div>'''
    html += _rec_block(recommendation)
    html += _route_detail_table(route)
    html += _BASE_FOOTER
    html += _WRAP_CLOSE

    return _send(settings, subject, html)


def send_daily_digest(settings, routes_data):
    """Send a morning digest of all tracked routes."""
    subject = f'✈️ Daily Flight Digest — {datetime.now().strftime("%B %d, %Y")}'

    status_map = {
        'BUY_NOW':    ('#dc2626', 'white'),
        'GOOD_TIME':  ('#16a34a', 'white'),
        'WAIT':       ('#ea580c', 'white'),
        'MONITOR':    ('#2563eb', 'white'),
        'MONITORING': ('#6b7280', 'white'),
    }

    rows_html = ''
    for rd in routes_data:
        route = rd['route']
        summary = rd.get('summary', {})
        rec = rd.get('recommendation', {})

        price = summary.get('current', 0)
        change = summary.get('change_1d', 0)
        change_str = f'{"↓" if change < 0 else "↑"}${abs(change):,.0f}' if change != 0 else '—'
        change_color = '#16a34a' if change < 0 else '#dc2626' if change > 0 else '#9ca3af'
        status = rec.get('status', 'MONITORING')
        bg, fg = status_map.get(status, ('#6b7280', 'white'))

        rows_html += f'''
        <tr style="border-bottom:1px solid #e5e7eb;">
          <td style="padding:12px 8px;font-weight:600;font-size:13px;">
            {route.get("name") or route["origin"] + " → " + route["destination"]}
          </td>
          <td style="padding:12px 8px;font-size:15px;font-weight:700;">${price:,.0f}</td>
          <td style="padding:12px 8px;color:{change_color};font-weight:600;font-size:13px;">
            {change_str}
          </td>
          <td style="padding:12px 8px;">
            <span style="background:{bg};color:{fg};padding:3px 10px;
                         border-radius:20px;font-size:11px;font-weight:700;white-space:nowrap;">
              {status.replace("_", " ")}
            </span>
          </td>
        </tr>'''

    html = _WRAP_OPEN
    html += _BASE_HEADER.format(
        title='Daily Flight Digest',
        subtitle=datetime.now().strftime('%A, %B %d, %Y — searched at 7 am ET'),
    )
    html += f'''
    <div style="border-radius:10px;overflow:hidden;border:1px solid #e5e7eb;margin-bottom:20px;">
      <table style="width:100%;border-collapse:collapse;">
        <thead>
          <tr style="background:#f9fafb;">
            <th style="padding:10px 8px;text-align:left;font-size:11px;color:#6b7280;
                       text-transform:uppercase;letter-spacing:.05em;">Route</th>
            <th style="padding:10px 8px;text-align:left;font-size:11px;color:#6b7280;
                       text-transform:uppercase;letter-spacing:.05em;">Price</th>
            <th style="padding:10px 8px;text-align:left;font-size:11px;color:#6b7280;
                       text-transform:uppercase;letter-spacing:.05em;">vs Yesterday</th>
            <th style="padding:10px 8px;text-align:left;font-size:11px;color:#6b7280;
                       text-transform:uppercase;letter-spacing:.05em;">Status</th>
          </tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>'''
    html += _BASE_FOOTER
    html += _WRAP_CLOSE

    return _send(settings, subject, html)


def send_test_email(settings):
    """Send a configuration test email."""
    subject = '✅ Flight Tracker — Email is Working'
    html = _WRAP_OPEN + _BASE_HEADER.format(
        title="It's Working!",
        subtitle='Your Flight Tracker email notifications are configured correctly.',
    ) + '''
    <div style="background:#f0fdf4;border:2px solid #86efac;border-radius:10px;
                padding:20px;text-align:center;margin-bottom:20px;">
      <p style="margin:0;font-size:15px;color:#16a34a;font-weight:600;">
        ✅ Gmail connection successful. You'll receive price alerts at this address.
      </p>
    </div>''' + _BASE_FOOTER + _WRAP_CLOSE

    return _send(settings, subject, html)
