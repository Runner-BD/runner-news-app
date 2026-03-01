from flask import Flask, render_template_string, request
import feedparser
import re

app = Flask(__name__)

# ===============================
# GLOBAL STORAGE
# ===============================
SAVED_SOURCES = []
LAST_FETCHED_NEWS = []

# ===============================
# CLEAN TEXT FUNCTION
# ===============================
def clean_text(text):
    if not text:
        return ""

    # remove HTML
    text = re.sub(r"<.*?>", "", text)

    # remove "আরও পড়ুন"
    text = re.sub(r"আরও পড়ুন[:：]?.*", "", text)

    # remove extra spaces
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ===============================
# FREE SMART SUMMARY (LEVEL 1)
# ===============================
def free_smart_summary(text):
    sentences = re.split(r"[।!?]", text)

    important = []
    keywords = ["নিহত", "হামলা", "বিস্ফোরণ", "সংঘর্ষ", "গ্রেফতার"]

    for s in sentences:
        if any(k in s for k in keywords):
            important.append(s.strip())

    if not important:
        important = sentences[:3]

    summary = "। ".join(important).strip()

    # character control
    if len(summary) > 900:
        summary = summary[:900]

    return summary


# ===============================
# COMBINED SUMMARY ENGINE
# ===============================
def generate_combined_summary(text):
    TARGET_MIN = 650
    TARGET_MAX = 900

    summary = free_smart_summary(text)

    if len(summary) > TARGET_MAX:
        summary = summary[:TARGET_MAX]

    return summary


# ===============================
# HOME PAGE
# ===============================
@app.route("/")
def home():
    return render_template_string(TEMPLATE,
        sources=SAVED_SOURCES,
        news_list=LAST_FETCHED_NEWS,
        final_summary=None
    )


# ===============================
# ADD SOURCE
# ===============================
@app.route("/add_source", methods=["POST"])
def add_source():
    url = request.form.get("rss_url")
    keywords = request.form.get("keywords", "")

    if url:
        SAVED_SOURCES.append({
            "url": url.strip(),
            "keywords": keywords.strip()
        })

    return home()


# ===============================
# DELETE SOURCE
# ===============================
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

    for src in SAVED_SOURCES:
        feed = feedparser.parse(src["url"])
        keywords = [k.strip() for k in src["keywords"].split(",") if k.strip()]

        for entry in feed.entries[:15]:
            title = clean_text(entry.get("title", ""))
            summary = clean_text(entry.get("summary", ""))

            full_text = title + " " + summary

            if keywords:
                if not any(k in full_text for k in keywords):
                    continue

            LAST_FETCHED_NEWS.append({
                "title": title,
                "summary": summary[:300],
                "source": src["url"]
            })

    return home()


# ===============================
# GENERATE SELECTED SUMMARY
# ===============================
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
    final_summary = generate_combined_summary(combined_text)

    return render_template_string(TEMPLATE,
        sources=SAVED_SOURCES,
        news_list=LAST_FETCHED_NEWS,
        final_summary=final_summary
    )


# ===============================
# SIMPLE UI TEMPLATE
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
  <small>{{ news.source }}</small>
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

# ===============================
# RUN
# ===============================
if __name__ == "__main__":
    app.run(debug=True)
