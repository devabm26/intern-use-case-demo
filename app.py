import os
import psycopg2
import psycopg2.extras
from flask import Flask, render_template_string, jsonify

app = Flask(__name__)

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "postgresql.thoughts-app.svc.cluster.local"),
    "database": os.environ.get("DB_NAME", "thoughts"),
    "user": os.environ.get("DB_USER", "thoughts"),
    "password": os.environ.get("DB_PASSWORD", "thoughts123"),
    "port": int(os.environ.get("DB_PORT", 5432)),
    "connect_timeout": 10,
}


def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)


def fetch_thoughts():
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    t.content,
                    t.author,
                    t.status,
                    t.thumbs_up,
                    t.thumbs_down,
                    (t.thumbs_up - t.thumbs_down) AS net_rating,
                    te.similarity_score,
                    t.created_at
                FROM thoughts t
                LEFT JOIN LATERAL (
                    SELECT similarity_score
                    FROM thought_evaluations
                    WHERE thought_id = t.id
                    ORDER BY evaluated_at DESC
                    LIMIT 1
                ) te ON true
                ORDER BY t.created_at DESC
            """)
            return cur.fetchall(), None
    except Exception as e:
        return None, str(e)
    finally:
        conn.close()


def fetch_summary():
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE status = 'APPROVED') AS approved,
                    COUNT(*) FILTER (WHERE status = 'REJECTED') AS rejected,
                    COUNT(*) FILTER (WHERE status = 'IN_REVIEW') AS in_review,
                    COUNT(*) FILTER (WHERE status = 'REMOVED') AS removed
                FROM thoughts
            """)
            return cur.fetchone(), None
    except Exception as e:
        return None, str(e)
    finally:
        conn.close()


TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Thoughts Dashboard</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Segoe UI', sans-serif; background: #f0f2f5; color: #333; }

    header {
      background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
      color: white;
      padding: 24px 32px;
    }
    header h1 { font-size: 1.8rem; font-weight: 700; letter-spacing: 0.5px; }
    header p  { margin-top: 4px; opacity: 0.7; font-size: 0.9rem; }

    .summary {
      display: flex;
      gap: 16px;
      padding: 24px 32px 0;
      flex-wrap: wrap;
    }
    .card {
      background: white;
      border-radius: 10px;
      padding: 20px 28px;
      flex: 1;
      min-width: 140px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.08);
      text-align: center;
    }
    .card .label { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; color: #888; margin-bottom: 8px; }
    .card .value { font-size: 2rem; font-weight: 700; }
    .card.total  .value { color: #1a1a2e; }
    .card.approved  .value { color: #27ae60; }
    .card.rejected  .value { color: #e74c3c; }
    .card.in_review .value { color: #f39c12; }
    .card.removed   .value { color: #95a5a6; }

    .table-section {
      margin: 24px 32px;
      background: white;
      border-radius: 10px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.08);
      overflow: hidden;
    }
    .table-section h2 {
      padding: 18px 24px;
      font-size: 1rem;
      border-bottom: 1px solid #eee;
      color: #1a1a2e;
    }

    .table-wrap { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
    thead th {
      background: #f8f9fa;
      padding: 12px 16px;
      text-align: left;
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: #666;
      border-bottom: 1px solid #eee;
      white-space: nowrap;
    }
    tbody tr { border-bottom: 1px solid #f0f0f0; transition: background 0.15s; }
    tbody tr:hover { background: #fafbff; }
    tbody td { padding: 12px 16px; vertical-align: middle; }

    .content-cell { max-width: 360px; }
    .content-text {
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
      line-height: 1.45;
    }
    .author { font-weight: 600; white-space: nowrap; }

    .badge {
      display: inline-block;
      padding: 3px 10px;
      border-radius: 12px;
      font-size: 0.72rem;
      font-weight: 600;
      letter-spacing: 0.3px;
      white-space: nowrap;
    }
    .badge-APPROVED  { background: #d5f5e3; color: #1e8449; }
    .badge-REJECTED  { background: #fce8e6; color: #c0392b; }
    .badge-IN_REVIEW { background: #fef9e7; color: #b7770d; }
    .badge-REMOVED   { background: #eaecee; color: #717d7e; }

    .num { text-align: right; font-variant-numeric: tabular-nums; }
    .net-pos { color: #27ae60; font-weight: 600; }
    .net-neg { color: #e74c3c; font-weight: 600; }
    .net-zero { color: #95a5a6; }

    .sim { font-variant-numeric: tabular-nums; }
    .sim-good { color: #27ae60; }
    .sim-mid  { color: #f39c12; }
    .sim-bad  { color: #e74c3c; }

    .error-box {
      margin: 24px 32px;
      background: #fce8e6;
      border: 1px solid #f5c6c6;
      border-radius: 10px;
      padding: 20px 24px;
      color: #c0392b;
    }
    .error-box h3 { margin-bottom: 8px; }
    .error-box code { font-size: 0.85rem; word-break: break-all; }

    footer {
      text-align: center;
      padding: 20px;
      font-size: 0.8rem;
      color: #aaa;
    }

    .refresh-btn {
      float: right;
      margin: 14px 24px;
      padding: 6px 14px;
      background: #0f3460;
      color: white;
      border: none;
      border-radius: 6px;
      cursor: pointer;
      font-size: 0.8rem;
    }
    .refresh-btn:hover { background: #16213e; }
  </style>
</head>
<body>

<header>
  <h1>Thoughts Dashboard</h1>
  <p>Reporting view &mdash; PostgreSQL @ {{ db_host }}</p>
</header>

{% if error %}
<div class="error-box">
  <h3>Database Connection Error</h3>
  <p>Could not connect to the database. Check your connection settings.</p>
  <br/>
  <code>{{ error }}</code>
</div>
{% else %}

<div class="summary">
  <div class="card total">
    <div class="label">Total</div>
    <div class="value">{{ summary.total }}</div>
  </div>
  <div class="card approved">
    <div class="label">Approved</div>
    <div class="value">{{ summary.approved }}</div>
  </div>
  <div class="card rejected">
    <div class="label">Rejected</div>
    <div class="value">{{ summary.rejected }}</div>
  </div>
  <div class="card in_review">
    <div class="label">In Review</div>
    <div class="value">{{ summary.in_review }}</div>
  </div>
  <div class="card removed">
    <div class="label">Removed</div>
    <div class="value">{{ summary.removed }}</div>
  </div>
</div>

<div class="table-section">
  <h2>All Thoughts ({{ thoughts | length }} records)
    <button class="refresh-btn" onclick="location.reload()">Refresh</button>
  </h2>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>Content</th>
          <th>Author</th>
          <th>Status</th>
          <th class="num">Thumbs Up</th>
          <th class="num">Thumbs Down</th>
          <th class="num">Net Rating</th>
          <th class="num">Similarity</th>
        </tr>
      </thead>
      <tbody>
        {% for t in thoughts %}
        {% set net = t.net_rating | int %}
        <tr>
          <td style="color:#aaa; font-size:0.8rem;">{{ loop.index }}</td>
          <td class="content-cell">
            <div class="content-text" title="{{ t.content }}">{{ t.content }}</div>
          </td>
          <td class="author">{{ t.author }}</td>
          <td>
            <span class="badge badge-{{ t.status }}">{{ t.status.replace('_', ' ') }}</span>
          </td>
          <td class="num">{{ t.thumbs_up }}</td>
          <td class="num">{{ t.thumbs_down }}</td>
          <td class="num {% if net > 0 %}net-pos{% elif net < 0 %}net-neg{% else %}net-zero{% endif %}">
            {% if net > 0 %}+{% endif %}{{ net }}
          </td>
          <td class="num sim {% if t.similarity_score is none %}{% elif t.similarity_score < 0.5 %}sim-good{% elif t.similarity_score < 0.85 %}sim-mid{% else %}sim-bad{% endif %}">
            {% if t.similarity_score is none %}
              &mdash;
            {% else %}
              {{ "%.4f" | format(t.similarity_score | float) }}
            {% endif %}
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>

{% endif %}

<footer>Thoughts Dashboard &mdash; {{ now }}</footer>

</body>
</html>
"""


@app.route("/")
def index():
    from datetime import datetime

    thoughts, error = fetch_thoughts()
    summary = None

    if not error:
        summary, sum_error = fetch_summary()
        if sum_error:
            error = sum_error

    return render_template_string(
        TEMPLATE,
        thoughts=thoughts or [],
        summary=summary,
        error=error,
        db_host=DB_CONFIG["host"],
        now=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


@app.route("/healthz")
def health():
    try:
        conn = get_db_connection()
        conn.close()
        return jsonify({"status": "ok", "db": "connected"})
    except Exception as e:
        return jsonify({"status": "error", "db": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting Thoughts Dashboard on http://0.0.0.0:{port}")
    print(f"Connecting to: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    app.run(host="0.0.0.0", port=port, debug=False)
