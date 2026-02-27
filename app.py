from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def summarize_news(title, content):
    try:
        prompt = f"""
        Summarize the following news in simple Bengali in 2–3 lines.

        Title: {title}
        Content: {content}
        """

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=120,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        print("OpenAI error:", e)
        return "Summary unavailable"


from flask import Flask, render_template_string, request, redirect
import sqlite3
import hashlib
import feedparser
import os
from openai import OpenAI

app = Flask(__name__)
DB_NAME = "runner.db"

# OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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

{% if news %}
<div class="box">
    <h3>Generated Bangla News</h3>
    <p><b>Heading:</b> {{news.heading}}</p>
    <p>{{news.body}}</p>
    <p><a href="{{news.link}}" target="_blank">Open Source</a></p>

    <button>Approve</button>
    <button>Cancel</button>
</div>
{% endif %}

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

def keyword_match(title, keywords):
    title_lower = title.lower()
    for kw in keywords.split(","):
        if kw.strip().lower() in title_lower:
            return True
    return False

def is_duplicate(headline_hash):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT 1 FROM news_history WHERE headline_hash=?", (headline_hash,))
    exists = c.fetchone()
    conn.close()
    return exists is not None

def save_headline(headline_hash):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO news_history (headline_hash) VALUES (?)",
            (headline_hash,)
        )
        conn.commit()
    except:
        pass
    conn.close()

def generate_bangla_summary(title):
    prompt = f"""
সংবাদ শিরোনাম: {title}

নির্দেশনা:
- 650 থেকে 900 অক্ষরের মধ্যে বাংলায় সংবাদ সারাংশ লিখুন
- নিরপেক্ষ ও পেশাদার ভাষা ব্যবহার করুন
- কোনো নেতিবাচক বা আক্রমণাত্মক শব্দ ব্যবহার করবেন না
- সংক্ষিপ্ত ও পরিষ্কার রাখুন
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
    )

    return response.choices[0].message.content.strip()

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

    for src in sources:
        rss_url = src[1]
        keywords = src[2]

        feed = feedparser.parse(rss_url)

        for entry in feed.entries[:10]:
            title = entry.title

            if keyword_match(title, keywords):
                headline_hash = hashlib.md5(title.encode()).hexdigest()

                if is_duplicate(headline_hash):
                    continue

                summary = generate_bangla_summary(title)
                save_headline(headline_hash)

                news_item = {
                    "heading": title,
                    "body": summary,
                    "link": entry.link
                }

                all_news.append(news_item)

    return render_template_string(
        HTML_PAGE,
        sources=sources,
        news=all_news
    )

# -----------------------
# MAIN
# -----------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)


