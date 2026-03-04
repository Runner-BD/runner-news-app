from flask import Flask, render_template_string, request
import feedparser
import re
import html
from datetime import datetime

app = Flask(__name__)

SAVED_SOURCES = []
LAST_FETCHED_NEWS = []

# ===============================
# CLEAN TEXT
# ===============================
def clean_text(text):
    if not text:
        return ""

    text = html.unescape(text)
    text = re.sub(r"<.*?>", "", text)
    text = re.sub(r"আরও পড়ুন[:：]?.*", "", text)
    text = re.sub(r"বিস্তারিত.*", "", text)
    text = re.sub(r"[\u200b\u200c\u200d\ufeff&nbsp;]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ===============================
# PRIORITY SCORING
# ===============================
def get_priority(text):
    high_words = [
        "নিহত","হামলা","বিস্ফোরণ","যুদ্ধ",
        "ক্ষেপণাস্ত্র","সংঘর্ষ","মারা গেছে"
    ]

    medium_words = [
        "গ্রেফতার","নির্বাচন","ঘোষণা","বৈঠক"
    ]

    score = 0

    for w in high_words:
        if w in text:
            score += 3

    for w in medium_words:
        if w in text:
            score += 1

    if score >= 3:
        return "HIGH", score
    elif score >= 1:
        return "MEDIUM", score
    else:
        return "LOW", score


# ===============================
# BUILD DRAFT SUMMARY (RICH)
# ===============================
def build_multi_segment_summary(selected_items):
    TARGET_MIN = 1200
    TARGET_MAX = 1800

    segments = []
    total_len = 0

    for item in selected_items:
        title = clean_text(item["title"])
        body = clean_text(item["summary"])

        short_body = body[:320]

        segment = f"🔹 {title}\n{short_body}"

        if total_len + len(segment) > TARGET_MAX:
            break

        segments.append(segment)
        total_len += len(segment)

        if total_len >= TARGET_MIN:
            break

    return "\n\n".join(segments)


# ===============================
# ROUTES
# ===============================
@app.route("/")
def home():
    return render_template_string(
        TEMPLATE,
        sources=SAVED_SOURCES,
        news_list=LAST_FETCHED_NEWS,
        draft_summary=None,
        final_summary=None
    )


@app.route("/add_source", methods=["POST"])
def add_source():
    url = request.form.get("rss_url")
    keywords = request.form.get("keywords", "")

    if url:
        SAVED_SOURCES.append({
            "url": url.strip(),
            "keywords": keywords.strip().lower()
        })

    return home()


@app.route("/delete_source/<int:index>")
def delete_source(index):
    if 0 <= index < len(SAVED_SOURCES):
        SAVED_SOURCES.pop(index)
    return home()


# ===============================
# FETCH NEWS
# ===============================
@app.route("/fetch_news")
def fetch_news():
    global LAST_FETCHED_NEWS
    LAST_FETCHED_NEWS = []

    try:
        for src in SAVED_SOURCES:
            feed = feedparser.parse(src["url"])
            keywords = [k.strip().lower() for k in src["keywords"].split(",") if k.strip()]

            for entry in feed.entries[:40]:
                title = clean_text(entry.get("title", ""))
                summary = clean_text(entry.get("summary", ""))

                if not title:
                    continue

                full_text = (title + " " + summary).lower()

                if keywords:
                    if not any(k in full_text for k in keywords):
                        continue

                priority, score = get_priority(full_text)

                try:
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        date_obj = datetime(*entry.published_parsed[:6])
                        nice_date = date_obj.strftime("%d %b %Y %I:%M %p")
                    else:
                        nice_date = "Unknown"
                except:
                    nice_date = "Unknown"

                LAST_FETCHED_NEWS.append({
                    "title": title,
                    "summary": summary[:400],
                    "source": src["url"],
                    "priority": priority,
                    "score": score,
                    "date": nice_date
                })

        priority_order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

        LAST_FETCHED_NEWS.sort(
            key=lambda x: (priority_order.get(x["priority"], 0), x["score"]),
            reverse=True
        )

    except Exception as e:
        print("❌ FETCH ERROR:", e)

    return home()


@app.route("/generate_selected", methods=["POST"])
def generate_selected():
    selected_indexes = request.form.getlist("selected_news")

    if not selected_indexes:
        return home()

    selected_items = []

    for idx in selected_indexes:
        try:
            selected_items.append(LAST_FETCHED_NEWS[int(idx)])
        except:
            pass

    draft_summary = build_multi_segment_summary(selected_items)

    return render_template_string(
        TEMPLATE,
        sources=SAVED_SOURCES,
        news_list=LAST_FETCHED_NEWS,
        draft_summary=draft_summary,
        final_summary=None
    )


@app.route("/finalize_summary", methods=["POST"])
def finalize_summary():
    edited_summary = request.form.get("edited_summary", "")

    return render_template_string(
        TEMPLATE,
        sources=SAVED_SOURCES,
        news_list=LAST_FETCHED_NEWS,
        draft_summary=None,
        final_summary=edited_summary
    )


# ===============================
# TEMPLATE
# ===============================
TEMPLATE = """
<h1>Runner News Dashboard</h1>

<h2>Add RSS Source</h2>
<form method="post" action="/add_source">
  RSS URL: <input name="rss_url" size="50">
  Keywords: <input name="keywords" size="40">
  <button>Add Source</button>
</form>

<h2>Saved Sources</h2>
{% for s in sources %}
  {{ s.url }} | Keywords: {{ s.keywords }}
  <a href="/delete_source/{{ loop.index0 }}">❌ Delete</a><br><br>
{% endfor %}

<a href="/fetch_news">🚀 Fetch News</a>

{% if news_list %}
<hr>
<form method="post" action="/generate_selected">
<h2>Select News</h2>

{% for news in news_list %}
<div style="border:1px solid #ccc;padding:10px;margin:10px 0;">
  <label>
    <input type="checkbox" name="selected_news" value="{{ loop.index0 }}">
    <strong>{{ news.title }}</strong>
  </label>
  <p>{{ news.summary }}</p>
  <small>
    Priority: <b>{{ news.priority }}</b> |
    Date: {{ news.date }} |
    Source: {{ news.source }}
  </small>
</div>
{% endfor %}

<button type="submit">🧠 Generate Draft Summary</button>
</form>
{% endif %}

{% if draft_summary %}
<hr>
<h2>📝 Edit Draft Summary</h2>

<form method="post" action="/finalize_summary">
<textarea name="edited_summary" rows="14" style="width:100%;">{{ draft_summary }}</textarea><br><br>
<button type="submit">✅ Finalize Summary</button>
</form>
{% endif %}

{% if final_summary %}
<hr>
<h2>📊 Final News Summary</h2>
<p>{{ final_summary }}</p>
<p><b>Total Characters:</b> {{ final_summary|length }}</p>
{% endif %}
"""

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting app on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)