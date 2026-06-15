import os
import psycopg2
from flask import Flask, render_template

app = Flask(__name__)

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "postgresql.thoughts-app.svc.cluster.local"),
    "database": os.environ.get("DB_NAME", "thoughts"),
    "user": os.environ.get("DB_USER", "thoughts"),
    "password": os.environ.get("DB_PASSWORD", "thoughts123"),
    "port": int(os.environ.get("DB_PORT", 5432)),
    "connect_timeout": 5,
}


def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)


def fetch_thoughts():
    try:
        conn = get_db_connection()
    except Exception as e:
        return None, str(e)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    t.content,
                    t.author,
                    t.status,
                    t.thumbs_up,
                    t.thumbs_down,
                    (t.thumbs_up - t.thumbs_down) AS net_rating,
                    te.similarity_score
                FROM thoughts t
                LEFT JOIN LATERAL (
                    SELECT similarity_score
                    FROM thought_evaluations
                    WHERE thought_id = t.id
                    ORDER BY evaluated_at DESC
                    LIMIT 1
                ) te ON true
                ORDER BY net_rating DESC, t.thumbs_up DESC
            """)
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            return [dict(zip(columns, row)) for row in rows], None
    except Exception as e:
        return None, str(e)
    finally:
        conn.close()


def fetch_summary():
    try:
        conn = get_db_connection()
    except Exception as e:
        return None, str(e)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE status = 'APPROVED') AS approved,
                    COUNT(*) FILTER (WHERE status = 'REJECTED') AS rejected,
                    COUNT(*) FILTER (WHERE status = 'IN_REVIEW') AS in_review,
                    COUNT(*) FILTER (WHERE status = 'REMOVED') AS removed
                FROM thoughts
            """)
            row = cur.fetchone()
            return {
                "total": row[0],
                "approved": row[1],
                "rejected": row[2],
                "in_review": row[3],
                "removed": row[4],
            }, None
    except Exception as e:
        return None, str(e)
    finally:
        conn.close()


@app.route("/")
def index():
    thoughts, thoughts_error = fetch_thoughts()
    summary, summary_error = fetch_summary()
    error = thoughts_error or summary_error
    return render_template(
        "index.html",
        thoughts=thoughts or [],
        summary=summary or {},
        error=error,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
