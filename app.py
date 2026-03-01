import os
import re
import sqlite3
import feedparser
import html
import math

from flask import Flask, request, redirect, render_template_string
from openai import OpenAI

# =========================
# FLASK SETUP
# =========================
app = Flask(__name__)
DB_NAME = "news.db"

# =========================
# OPENAI SETUP
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
# CATEGORY DETECTOR (Option C)
# =========================
def detect_category(text):
    text = text.lower()

    if any(k in text for k in ["রাজনীতি", "নির্বাচন", "সরকার", "মন্ত্রী"]):
        return "Politics"
    if any(k in text for k in ["অর্থনীতি", "ব্যাংক", "টাকা", "বাজার"]):
        return "Business & Finance"
    if any(k in text for k in ["প্রযুক্তি", "টেক", "মোবাইল", "এআই"]):
        return "Science & Technology"
    if any(k in text for k in ["স্বাস্থ্য", "হাসপাতাল", "রোগ", "চিকিৎসা"]):
        return "Health"

    return "Others"

def assign_priority(category):
    if category in ["Politics", "Business & Finance"]:
        return "HIGH"
    return "MEDIUM"

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
    if not keyword_string:
        return True

    text = f"{title} {description}".lower()
    keywords = [k.strip().lower() for k in keyword_string.split(",") if k.strip()]
    return any(k in text for k in keywords)

# =========================
# SUMMARY ENGINE
# =========================
def free_combined_summary(text):
    text = clean_html(text)
    if len(text) > 900:
        text = text[:900]
    return text

def generate_combined_summary(text):
    if not client:
        return free_combined_summary(text)

    try:
        prompt = f"""
নিচের সব খবর মিলিয়ে ৬৫০–৯০০ অক্ষরের মধ্যে একটি সংক্ষিপ্ত,
পেশাদার বাংলা নিউজ সারাংশ লিখো।

{text}
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=500,
        )

        result = response.choices[0].message.content.strip()
        return result if result else free_combined_summary(text)

    except Exception as e:
        print("❌ AI SUMMARY ERROR:", e)
        return free_combined_summary(text)

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
<h2>Select News</h2>
<form method="post" action="/generate">
{% for n in news %}
<hr>
<input type="checkbox" name="selected" value="{{loop.index0}}">
<b>{{n.heading}}</b><br>
Category: {{n.category}} | Priority: {{n.priority}}<br>
{% endfor %}
<br>
<button type="submit">🧠 Generate Final Summary</button>
</form>
{% endif %}

{% if final_summary %}
<hr>
<h2>📊 Final News Summary</h2>
<p>{{final_summary}}</p>

<b>Total Characters:</b> {{char_count}}<br>
<b>Slides Needed:</b> {{slides}}<br>
<b>Seconds per Slide:</b> {{seconds}}<br>
{% endif %}
"""

# =========================
# ROUTES
# =========================
@app.route("/")
def home():
    return render_template_string(HTML_PAGE, sources=get_sources(), news=None)

@app.route("/add_source", methods=["POST"])
def add_source():
    url = request.form.get("url", "").strip()
    keywords = request.form.get("keywords", "").strip()

    if not url:
        return redirect("/")

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO sources (url, keywords) VALUES (?, ?)",
        (url, keywords)
    )
    conn.commit()
    conn.close()

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

    for src in sources:
        rss_url = src[1]
        keyword_string = src[2] or ""

        feed = feedparser.parse(rss_url)
        source_name = rss_url.replace("https://", "").replace("http://", "").split("/")[0]

        for entry in feed.entries[:15]:
            title = entry.get("title", "")
            link = entry.get("link", "#")
            description = entry.get("summary", "")

            if not title:
                continue

            if not keyword_match(title, description, keyword_string):
                continue

            category = detect_category(title + " " + description)
            priority = assign_priority(category)

            all_news.append({
                "heading": title,
                "link": link,
                "category": category,
                "priority": priority,
                "text": clean_html(description)
            })

    app.config["LAST_NEWS"] = all_news

    return render_template_string(
        HTML_PAGE,
        sources=sources,
        news=all_news
    )

@app.route("/generate", methods=["POST"])
def generate():
    selected_ids = request.form.getlist("selected")
    news_list = app.config.get("LAST_NEWS", [])

    combined_text = ""

    for sid in selected_ids:
        idx = int(sid)
        combined_text += news_list[idx]["heading"] + ". "
        combined_text += news_list[idx]["text"] + " "

    final_summary = generate_combined_summary(combined_text)

    char_count = len(final_summary)
    slides = max(1, math.ceil(char_count / 130))
    seconds = round(60 / slides, 2)

    return render_template_string(
        HTML_PAGE,
        sources=get_sources(),
        news=news_list,
        final_summary=final_summary,
        char_count=char_count,
        slides=slides,
        seconds=seconds
    )

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
