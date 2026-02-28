import os
import re
import sqlite3
import hashlib
import feedparser

from flask import Flask, request, redirect, render_template_string

# =========================
# FLASK SETUP
# =========================
app = Flask(__name__)
DB_NAME = "news.db"

# =========================
# OPENAI SETUP (SAFE)
# =========================
from openai import OpenAI

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
    print("⚠️ OPENAI_API_KEY missing — using free mode")

# =========================
# DATABASE
# =========================
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

    conn.commit()
    conn.close()

init_db()

# =========================
# HELPERS
# =========================
def get_sources():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM sources")
    data = c.fetchall()
    conn.close()
    return data


def clean_html(text):
    if not text:
        return ""
    return re.sub("<[^<]+?>", "", text)


# =========================
# FREE SMART SUMMARY (WORKS WITHOUT AI)
# =========================
def free_smart_summary(title, description=""):
    text = description if description else title

    text = clean_html(text).strip()

    if not text:
        return "সারাংশ তৈরি করা যায়নি।"

    # make short
    if len(text) > 220:
        text = text[:220] + "..."

    return f"সংক্ষিপ্ত সংবাদ: {text}"


# =========================
# AI SUMMARY
# =========================
def generate_bangla_summary(title, description=""):
    if not client:
        return free_smart_summary(title, description)

    try:
        content_text = f"""
নিচের সংবাদটি ২-৩ লাইনে সংক্ষিপ্ত বাংলায় লিখো।

শিরোনাম: {title}
বিস্তারিত: {description}
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": content_text}],
            temperature=0.4,
            max_tokens=180,
        )

        text = response.choices[0].message.content.strip()

        if not text:
            return free_smart_summary(title, description)

        return text

    except Exception as e:
        print("❌ OPENAI ERROR:", e)
        return free_smart_summary(title, description)


# =========================
# HTML
# =========================
HTML_PAGE = """
<h1>Runner News Dashboard</h1>

<h2>Add RSS Source</h2>
<form method="post" action="/add_source">
    RSS URL: <input name="url" size="50">
    Keywords: <input name="keywords" size="50">
    <button type="submit">Add Source</button>
</form>

<h2>Saved Sources</h2>
{% for s in sources %}
<p>{{s[1]}} | Keywords: {{s[2]}}</p>
{% endfor %}

<form method="post" action="/fetch">
    <button type="submit">Fetch News</button>
</form>

{% if news %}
<h2>Generated Bangla News</h2>
{% for n in news %}
<hr>
<b>Heading:</b> {{n.heading}}<br><br>
{{n.body}}<br><br>
<a href="{{n.link}}" target="_blank">Open Source</a>
{% endfor %}
{% endif %}

<p>⚠️ If AI is unavailable, a basic summary is shown.</p>
"""

# =========================
# ROUTES
# =========================
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

                # description safe extract
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


# =========================
# MAIN
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
