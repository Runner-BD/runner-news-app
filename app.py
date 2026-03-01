import os
import re
import sqlite3
import feedparser
import html

from flask import Flask, request, redirect, render_template_string
from openai import OpenAI

# =========================
# FLASK SETUP
# =========================
app = Flask(__name__)
DB_NAME = "news.db"

# =========================
# OPENAI SETUP (SAFE)
# =========================
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
            url TEXT UNIQUE,
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
    c.execute("SELECT * FROM sources ORDER BY id DESC")
    data = c.fetchall()
    conn.close()
    return data


def delete_source_db(source_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM sources WHERE id=?", (source_id,))
    conn.commit()
    conn.close()


def clean_html(text):
    if not text:
        return ""
    text = re.sub("<[^<]+?>", "", text)
    text = html.unescape(text)
    return text.strip()


def keyword_match(title, description, keyword_string):
    """Check if any keyword exists in title or description"""
    if not keyword_string:
        return False

    text = f"{title} {description}".lower()
    keywords = [k.strip().lower() for k in keyword_string.split(",") if k.strip()]

    return any(k in text for k in keywords)

# =========================
# FREE SMART SUMMARY
# =========================
def free_smart_summary(title, description=""):
    text = description if description else title
    text = clean_html(text)

    if not text:
        return "সারাংশ তৈরি করা যায়নি।"

    if len(text) > 260:
        text = text[:260] + "..."

    return f"সংক্ষিপ্ত সংবাদ: {text}"

# =========================
# AI SUMMARY
# =========================
def generate_bangla_summary(title, description=""):
    if not client:
        return free_smart_summary(title, description)

    try:
        content_text = f"""
নিচের সংবাদটি সংক্ষিপ্ত, পরিষ্কার ও পেশাদার বাংলায় লিখো (৬৫০–৯০০ অক্ষরের মধ্যে)।

শিরোনাম: {title}
বিস্তারিত: {clean_html(description)}
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": content_text}],
            temperature=0.4,
            max_tokens=400,
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
<p>
{{s[1]}} | Keywords: {{s[2]}}
<form method="post" action="/delete_source" style="display:inline;">
    <input type="hidden" name="id" value="{{s[0]}}">
    <button type="submit">❌ Delete</button>
</form>
</p>
{% endfor %}

<form method="post" action="/fetch">
    <button type="submit">🚀 Fetch News</button>
</form>

{% if news %}
<h2>Generated Bangla News</h2>
{% for n in news %}
<hr>
<b>Heading:</b> {{n.heading}}<br><br>

{{n.body}}<br><br>

<b>Source:</b> {{n.source}}<br>
<b>Published:</b> {{n.published}}<br><br>

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
    url = request.form.get("url", "").strip()
    keywords = request.form.get("keywords", "").strip()

    if not url:
        return redirect("/")

    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute(
            "INSERT OR IGNORE INTO sources (url, keywords) VALUES (?, ?)",
            (url, keywords)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print("❌ INSERT ERROR:", e)

    return redirect("/")


@app.route("/delete_source", methods=["POST"])
def delete_source():
    source_id = request.form.get("id")
    if source_id:
        delete_source_db(source_id)
    return redirect("/")


@app.route("/fetch", methods=["POST"])
def fetch_news():
    sources = get_sources()
    all_news = []

    try:
        for src in sources:
            rss_url = src[1]
            keyword_string = src[2] or ""

            feed = feedparser.parse(rss_url)

            if not feed.entries:
                continue

            source_name = rss_url.replace("https://", "").replace("http://", "").split("/")[0]

            matched_count = 0
            fallback_count = 0

            for entry in feed.entries[:20]:
                title = entry.get("title", "")
                link = entry.get("link", "#")

                description = ""
                if hasattr(entry, "summary"):
                    description = entry.summary
                elif hasattr(entry, "description"):
                    description = entry.description

                published = entry.get("published", "") or entry.get("pubDate", "")

                if not title:
                    continue

                is_match = keyword_match(title, description, keyword_string)

                # ✅ PRIORITY NEWS
                if is_match and matched_count < 5:
                    summary = generate_bangla_summary(title, description)

                    all_news.append({
                        "heading": title,
                        "body": summary,
                        "link": link,
                        "source": source_name,
                        "published": published
                    })
                    matched_count += 1
                    continue

                # ✅ FALLBACK NEWS (prevents empty screen)
                if not is_match and fallback_count < 3:
                    summary = generate_bangla_summary(title, description)

                    all_news.append({
                        "heading": title,
                        "body": summary,
                        "link": link,
                        "source": source_name,
                        "published": published
                    })
                    fallback_count += 1

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
