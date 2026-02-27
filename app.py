from flask import Flask, render_template_string, request, redirect
import sqlite3
import hashlib

app = Flask(__name__)
DB_NAME = "runner.db"

# -----------------------
# DATABASE SETUP
# -----------------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Sources table
    c.execute("""
    CREATE TABLE IF NOT EXISTS sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT,
        keywords TEXT
    )
    """)

    # News history (for future dedup)
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
    <h3>Add News Source</h3>
    <form method="post" action="/add_source">
        <label>Source URL:</label>
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
    <h3>Fetch News (Demo)</h3>
    <form method="post" action="/fetch">
        <button type="submit">Fetch News</button>
    </form>
</div>

{% if news %}
<div class="box">
    <h3>Generated News</h3>
    <p><b>Heading:</b> {{news.heading}}</p>
    <p>{{news.body}}</p>

    <button>Approve</button>
    <button>Edit</button>
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
    # DEMO news (real scraping later)
    headline = "বাংলাদেশে নতুন অর্থনৈতিক অগ্রগতি"

    # create hash for future dedup
    headline_hash = hashlib.md5(headline.encode()).hexdigest()

    demo_news = {
        "heading": headline,
        "body": "বাংলাদেশের অর্থনীতি সাম্প্রতিক সময়ে উল্লেখযোগ্য উন্নতি অর্জন করেছে। বিভিন্ন খাতে প্রবৃদ্ধি বৃদ্ধি পেয়েছে এবং বিশেষজ্ঞরা আশা করছেন এই ধারা অব্যাহত থাকবে।"
    }

    sources = get_sources()
    return render_template_string(HTML_PAGE, sources=sources, news=demo_news)

# -----------------------
# MAIN
# -----------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
