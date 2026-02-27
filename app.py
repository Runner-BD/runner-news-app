from flask import Flask, request, jsonify
import sqlite3
import hashlib
import datetime

app = Flask(__name__)

DB_NAME = "runner.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            hash TEXT UNIQUE,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

@app.route("/")
def home():
    return "Runner News API is running"

@app.route("/add_news", methods=["POST"])
def add_news():
    title = request.json.get("title")
    news_hash = hashlib.md5(title.encode()).hexdigest()

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("SELECT * FROM news WHERE hash=?", (news_hash,))
    exists = c.fetchone()

    if exists:
        conn.close()
        return jsonify({"status": "duplicate"})

    c.execute(
        "INSERT INTO news (title, hash, created_at) VALUES (?, ?, ?)",
        (title, news_hash, datetime.datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

    return jsonify({"status": "saved"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=81)