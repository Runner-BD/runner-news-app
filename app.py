# =============================================
# Runner News Dashboard — Level‑2 Lite (STABLE FIX)
# Copy‑paste the ENTIRE file and run
# =============================================

from flask import Flask, render_template_string, request
import feedparser
import re
import html
from datetime import datetime

app = Flask(__name__)

# ---------------- GLOBAL STATE ----------------
SAVED_SOURCES = []
LAST_FETCHED_NEWS = []


# =============================================
# TEXT CLEANER
# =============================================
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


# =============================================
# PRIORITY + VIRAL SCORE
# =============================================
def get_priority_and_viral(text):
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
            score += 5

    for w in medium_words:
        if w in text:
            score += 2

    # number boost
    if re.search(r"\d+", text):
        score += 1

    if score >= 5:
        priority = "HIGH"
    elif score >= 2:
        priority = "MEDIUM"
    else:
        priority = "LOW"

    return priority, score


# =============================================
# RICH SUMMARY (EDITOR STAGE)
# =============================================
def smart_summary_rich(text):
    TARGET_MIN = 1200
    TARGET_MAX = 1800

    sentences = re.split(r"[।!?]", text)
    sentences = [clean_text(s) for s in sentences if len(s.strip()) > 30]

    if not sentences:
        return text[:TARGET_MAX]

    priority_words = [
        "নিহত","হামলা","বিস্ফোরণ","সংঘর্ষ",
        "ক্ষেপণাস্ত্র","যুদ্ধ","গ্রেফতার"
    ]

    scored = []

    for s in sentences:
        score = sum(3 for w in priority_words if w in s)
        score += len(s) / 100
        scored.append((score, s))

    scored.sort(reverse=True, key=lambda x: x[0])

    selected = []
    total_len = 0

    for score, sent in scored:
        block = sent + "।"

        if total_len + len(block) > TARGET_MAX:
            continue

        selected.append(block)
        total_len += len(block)

        if total_len >= TARGET_MIN:
            break

    if not selected:
        return text[:TARGET_MAX]

    return " ".join(selected)[:TARGET_MAX]


# =============================================
# MULTI‑SEGMENT BUILDER
# =============================================
def build_multi_segment_summary(selected_items):
    segments = []

    for item in selected_items:
        title = clean_text(item["title"])
        body = clean_text(item["summary"])

        rich = smart_summary_rich(title + " " + body)

        badge = "🚨 BREAKING" if item["priority"] == "HIGH" else "🔹 UPDATE"

        segment = f"{badge}\n{title}\n{rich}"
        segments.append(segment)

    return "\n\n".join(segments)


# =============================================
# DUPLICATE KILLER
# =============================================
def is_duplicate(title, seen_titles):
    base = title[:60].lower()
    if base in seen_titles:
        return True
    seen_titles.add(base)
    return False


# =============================================
# ROUTES
# =============================================
@app.route("/")
def home():
    return render_template_string(
        TEMPLATE,
        sources=SAVED_SOURCES,
        news_list=LAST_FETCHED_NEWS,
        final_summary=None,
        draft_summary=None
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


# =============================================
# FETCH NEWS (STABLE)
# =============================================
@app.route("/fetch_news")
def fetch_news():
    global LAST_FETCHED_NEWS
    LAST_FETCHED_NEWS = []
    seen_titles = set()

    try:
        for src in SAVED_SOURCES:
            feed = feedparser.parse(src["url"])

            if not feed.entries:
                continue

            keywords = [k.strip().lower() for k in src["keywords"].split(",") if k.strip()]

            for entry in feed.entries[:40]:
                title = clean_text(entry.get("title", ""))
                summary = clean_text(entry.get("summary", ""))

                if not title:
                    continue

                if is_duplicate(title, seen_titles):
                    continue

                full_text = (title + " " + summary).lower()

                keyword_match = any(k in full_text for k in keywords) if keywords else True

                priority, viral_score = get_priority_and_viral(full_text)

                if keywords and not keyword_match and priority != "HIGH":
                    continue

                # safe date
                try:
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        date_obj = datetime(*entry.published_parsed[:6])
                        nice_date = date_obj.strftime("%d %b %Y %I:%M %p")
                    else:
                        nice_date = "Unknown"
                except Exception:
                    nice_date = "Unknown"

                LAST_FETCHED_NEWS.append({
                    "title": title,
                    "summary": summary[:400],
                    "source": src["url"],
                    "priority": priority,
                    "score": viral_score,
                    "date": nice_date
                })

        priority_order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

        LAST_FETCHED_NEWS.sort(
            key=lambda x: (priority_order.get(x["priority"], 0), x["score"]),
            reverse=True
        )

    except Exception as e:
        print("FETCH ERROR:", e)

    return home()


# =============================================
@app.route("/generate_selected", methods=["POST"])
def generate_selected():
    selected_indexes = request.form.getlist("selected_news")

    if not selected_indexes:
        return home()

    selected_items = []

    for idx in selected_indexes:
        try:
            selected_items.append(LAST_FETCHED_NEWS[int(idx)])
        except Exception:
            pass

    draft_summary = build_multi_segment_summary(selected_items)

    return render_template_string(
        TEMPLATE,
        sources=SAVED_SOURCES,
        news_list=LAST_FETCHED_NEWS,
        draft_summary=draft_summary,
        final_summary=None
    )


# =============================================
@app.route("/finalize_summary", methods=["POST"])
def finalize_summary():
    edited_summary = request.form.get("edited_summary", "")

    return render_template_string(
        TEMPLATE,
        sources=SAVED_SOURCES,
        news_list=LAST_FETCHED_NEWS,
        final_summary=edited_summary,
        draft_summary=None
    )


# =============================================
# TEMPLATE (SAFE + CLEAN)
# =============================================
TEMPLATE = """
<h1>Runner News Dashboard — Level‑2 Lite</h1>

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
    Viral Score: {{ news.score }} |
    Date: {{ news.date }}
  </small>
</div>
{% endfor %}

<button type="submit">🧠 Generate Draft Summary</button>
</form>
{% endif %}

{% if draft_summary %}
<hr>
<h2>📝 Edit Draft</h2>
<form method="post" action="/finalize_summary">
<textarea name="edited_summary" rows="16" style="width:100%;">{{ draft_summary }}</textarea><br><br>
<button type="submit">✅ Finalize Summary</button>
</form>
{% endif %}

{% if final_summary %}
<hr>
<h2>📊 Final News Summary</h2>
<p style="white-space:pre-line;">{{ final_summary }}</p>
<p><b>Total Characters:</b> {{ final_summary|length }}</p>
{% endif %}
"""


# =============================================
if __name__ == "__main__":
    print("Starting Runner News Dashboard...")
    app.run(debug=True, port=5000)
