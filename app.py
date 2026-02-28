import os
import sqlite3
import hashlib
import feedparser
from flask import Flask, render_template_string, request, redirect
from openai import OpenAI

# -----------------------
# APP CONFIG
# -----------------------
app = Flask(__name__)
DB_NAME = "runner.db"

# -----------------------
# OPENAI SAFE INIT
# -----------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = None
if OPENAI_API_KEY:
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        print("✅ OpenAI client initialized")
    except Exception as e:
        print("❌ OpenAI init failed:", e)
        client = None
else:
    print("⚠️ OPENAI_API_KEY missing")

# -----------------------
# FREE FALLBACK SUMMARY
# -----------------------
def free_smart_summary(title):
    if not title:
        return "সারাংশ তৈরি করা যায়নি।"

    summary = title.strip()

    if len(summary) > 120:
        summary = summary[:120] + "..."

    return f"সংক্ষিপ্ত সংবাদ: {summary}"


# -----------------------
# AI SUMMARY (SAFE)
# -----------------------
def generate_bangla_summary(title, description=""):
    if not client:
        return free_smart_summary(title)

    try:
        content_text = f"শিরোনাম: {title}\nবিস্তারিত: {description}"

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": content_text}],
            temperature=0.4,
            max_tokens=500,
        )

        text = response.choices[0].message.content.strip()

        if not text:
            return free_smart_summary(title)

        return text

    except Exception as e:
        print("❌ OPENAI ERROR:", e)
        return free_smart_summary(title)


# -----------------------
# DATABASE SETUP
# -----------------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT,
        keywords TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS news_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        headline_hash TEXT UNIQUE
    )
    """)

    conn.commit()
    conn.close()

init_db()

# -----------------------
# HTML TEMPLATE
# -----------------------
HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Runner News Dashboard</title>
    <style>
        body { font-family: Arial; padding: 20px; }
        input { width: 100%; padding: 8px; margin: 5px 0; }
        button { padding: 10px 15px; margin-top: 10px; }
        .box { border: 1px solid #ccc; padding: 15px; margin-top: 20px; }
    </style>
</head>
<body>

<h1>🏃 Runner News Dashboard</h1>

<div class="box">
    <h3>Add RSS Source</h3>
    <form method="post" action="/add_source">
        <label>RSS URL:</label>
        <input name="url" required>

        <label>Keywords (comma separated):</label>
        <input name="keywords" required>

        <button type="submit">Add Source</button>
    </form>
</div>

<div class="box">
    <h3>Saved Sources</h3>
    <ul>
    {% for s in sources %}
        <li>{{s[1]}} | Keywords: {{s[2]}}</li>
    {% endfor %}
    </ul>
</div>

<div class="box">
    <h3>Fetch News</h3>
    <form method="post" action="/fetch">
        <button type="submit">Fetch News</button>
    </form>
</div>

<div class="box">
    <h3>Generated Bangla News</h3>

    {% if news %}
        {% for item in news %}
            <div style="margin-bottom:15px; padding:10px; border:1px solid #ddd;">
                <p><b>Heading:</b> {{item.heading}}</p>
                <p>{{item.body}}</p>

                <p style="color: gray; font-size: 12px;">
                ⚠️ If AI is unavailable, a basic summary is shown.
                </p>

                <p><a href="{{item.link}}" target="_blank">Open Source</a></p>
            </div>
        {% endfor %}
    {% else %}
        <p>No news found.</p>
    {% endif %}
</div>

</body>
</html>
"""

# -----------------------
# HELPERS
# -----------------------
def get_sources():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM sources")
    rows = c.fetchall()
    conn.close()
    return rows


# -----------------------
# ROUTES
# -----------------------
@app.route("/")
def home():
    sources = get_sources()
    return render_template_string(HTML_PAGE, sources=sources, news=None)


@app.route("/add_source", methods=["POST"])
def add_source():
    url = request.form.get("url")
    keywords = request.form.get("keywords")

    if not url or not keywords:
        return redirect("/")

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "INSERT INTO sources (url, keywords) VALUES (?, ?)",
        (url, keywords)
    )
    conn.commit()
    conn.close()

    return redirect("/")


@app.route("/fetch", methods=["POST"])
def fetch_news():
    sources = get_sources()
    all_news = []

    try:
        for src in sources:
            rss_url = src[1]

            feed = feedparser.parse(rss_url)

            if not feed.entries:
                continue

            for entry in feed.entries[:10]:
                title = entry.get("title", "")
                link = entry.get("link", "#")

                description = ""
                if hasattr(entry, "summary"):
                    description = entry.summary
                elif hasattr(entry, "description"):
                    description = entry.description

                if not title:
                    continue

                summary = generate_bangla_summary(title, description)

                all_news.append({
                    "heading": title,
                    "body": summary,
                    "link": link
                })

    except Exception as e:
        print("❌ FETCH ERROR:", e)

    return render_template_string(
        HTML_PAGE,
        sources=sources,
        news=all_news
    )


# -----------------------
# MAIN
# -----------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
