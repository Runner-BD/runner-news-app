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
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
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
# SMART BANGLA SUMMARY
# ===============================
def smart_summary(text):
    TARGET_MIN = 650
    TARGET_MAX = 900

    sentences = re.split(r"[।!?]", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

    priority_words = [
        "নিহত","হামলা","বিস্ফোরণ","সংঘর্ষ",
        "গ্রেফতার","ক্ষেপণাস্ত্র","যুদ্ধ"
    ]

    scored = []

    for s in sentences:
        score = sum(1 for w in priority_words if w in s)
        scored.append((score, s))

    scored.sort(reverse=True, key=lambda x: (x[0], len(x[1])))

    selected = []
    total_len = 0

    for score, sent in scored:
        if total_len < TARGET_MAX:
            selected.append(sent)
            total_len += len(sent)
        else:
            break

    if not selected:
        selected = sentences[:5]

    summary = "। ".join(selected).strip()

    if len(summary) < TARGET_MIN:
        for s in sentences:
            if s not in selected:
                summary += "। " + s
                if len(summary) >= TARGET_MIN:
                    break

    summary = summary[:TARGET_MAX]

    return summary


# ===============================
# ROUTES
# ===============================
@app.route("/")
def home():
    return render_template_string(
        TEMPLATE,
        sources=SAVED_SOURCES,
        news_list=LAST_FETCHED_NEWS,
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
# FETCH NEWS (PRO LEVEL)
# ===============================
@app.route("/fetch_news")
def fetch_news():
    global LAST_FETCHED_NEWS
    LAST_FETCHED_NEWS = []

    try:
        for src in SAVED_SOURCES:
            feed = feedparser.parse(src["url"])
            keywords = [k.strip() for k in src["keywords"].split(",") if k.strip()]

            for entry in feed.entries[:25]:
                title = clean_text(entry.get("title", ""))
                summary = clean_text(entry.get("summary", ""))

                full_text = (title + " " + summary).lower()

                # keyword filter
                if keywords:
                    if not any(k.lower() in full_text for k in keywords):
                        continue

                # priority
                priority, score = get_priority(full_text)

                # date
                try:
                    published = entry.get("published", "")
                    date_obj = datetime(*entry.published_parsed[:6])
                    nice_date = date_obj.strftime("%d %b %Y %I:%M %p")
                except:
                    nice_date = "Unknown"

                LAST_FETCHED_NEWS.append({
                    "title": title,
                    "summary": summary[:350],
                    "source": src["url"],
                    "priority": priority,
                    "score": score,
                    "date": nice_date
                })

        # 🔥 SORT BY PRIORITY + SCORE
        LAST_FETCHED_NEWS.sort(
            key=lambda x: (x["score"]),
            reverse=True
        )

    except Exception as e:
        print("❌ FETCH ERROR:", e)

    return home()


@app.route("/generate_selected", methods=["POST"])
def generate_selected():
    selected = request.form.getlist("selected_news")

    if not selected:
        return home()

    combined_parts = []

    for idx in selected:
        try:
            item = LAST_FETCHED_NEWS[int(idx)]
            combined_parts.append(item["title"] + " " + item["summary"])
        except:
            pass

    combined_text = " ".join(combined_parts)
    final_summary = smart_summary(combined_text)

    return render_template_string(
        TEMPLATE,
        sources=SAVED_SOURCES,
        news_list=LAST_FETCHED_NEWS,
        final_summary=final_summary
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

<button type="submit">🧠 Generate Final Summary</button>
</form>
{% endif %}

{% if final_summary %}
<hr>
<h2>📊 Final News Summary</h2>
<p>{{ final_summary }}</p>
<p><b>Total Characters:</b> {{ final_summary|length }}</p>
{% endif %}
"""

if __name__ == "__main__":
    app.run(debug=True)
