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
        "ক্ষেপণাস্ত্র","সংঘর্ষ","মারা"
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
# 🔥 SMART SUMMARY ENGINE (DRAFT)
# 1200–1800 chars for editing
# ===============================
def smart_summary(text, target_min=1200, target_max=1800):
    if not text:
        return ""

    sentences = re.split(r"[।!?]", text)
    sentences = [clean_text(s) for s in sentences if len(s.strip()) > 25]

    if not sentences:
        return text[:target_max]

    priority_words = [
        "নিহত","হামলা","বিস্ফোরণ","সংঘর্ষ",
        "ক্ষেপণাস্ত্র","যুদ্ধ","আহত","মারা"
    ]

    scored = []

    for i, s in enumerate(sentences):
        score = 0

        score += sum(3 for w in priority_words if w in s)

        if i < 2:
            score += 2

        score += min(len(s) // 60, 3)

        scored.append((score, i, s))

    scored.sort(reverse=True)

    selected_indexes = sorted([i for _, i, _ in scored[:14]])
    selected_sentences = [sentences[i] for i in selected_indexes]

    summary = "। ".join(selected_sentences).strip()

    if len(summary) < target_min:
        for s in sentences:
            if s not in selected_sentences:
                summary += "। " + s
                if len(summary) >= target_min:
                    break

    return summary[:target_max]


# ===============================
# PROFESSIONAL MULTI-SEGMENT
# ===============================
def build_multi_segment_summary(selected_items):
    segments = []

    for item in selected_items:
        title = clean_text(item["title"])
        body = clean_text(item["summary"])

        detailed = smart_summary(title + " " + body, 350, 550)

        segment = f"🔹 {title}\n{detailed}"
        segments.append(segment)

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

                keyword_match = any(k in full_text for k in keywords) if keywords else True

                priority, score = get_priority(full_text)

                if keywords and not keyword_match and priority != "HIGH":
                    continue

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


# ===============================
# GENERATE DRAFT
# ===============================
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


# ===============================
# FINALIZE
# ===============================
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
# TEMPLATE (CLEAN + PROFESSIONAL)
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
<h2>📝 Edit & Compress Summary for Final Video</h2>

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

if __name__ == "__main__":
    app.run(debug=True)
