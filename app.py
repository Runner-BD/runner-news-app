from flask import Flask, render_template_string, request
import feedparser
import re
import html

app = Flask(__name__)

SAVED_SOURCES = []
LAST_FETCHED_NEWS = []

# ===============================
# CLEAN TEXT (STRONG VERSION)
# ===============================
def clean_text(text):
    if not text:
        return ""

    # decode HTML entities  ✅ VERY IMPORTANT
    text = html.unescape(text)

    # remove HTML tags
    text = re.sub(r"<.*?>", "", text)

    # remove 'আরও পড়ুন'
    text = re.sub(r"আরও পড়ুন[:：]?.*", "", text)

    # remove weird unicode spaces
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)

    # normalize spaces
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ===============================
# SMART BANGLA SUMMARY (FREE)
# ===============================
def smart_summary(text):
    TARGET_MIN = 650
    TARGET_MAX = 900

    sentences = re.split(r"[।!?]", text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

    # priority keywords
    priority_words = [
        "নিহত","হামলা","বিস্ফোরণ","সংঘর্ষ",
        "গ্রেফতার","মারা","ক্ষেপণাস্ত্র","যুদ্ধ"
    ]

    scored = []

    for s in sentences:
        score = sum(1 for w in priority_words if w in s)
        scored.append((score, s))

    # sort by importance
    scored.sort(reverse=True, key=lambda x: (x[0], len(x[1])))

    selected = []
    total_len = 0

    for score, sent in scored:
        if total_len < TARGET_MAX:
            selected.append(sent)
            total_len += len(sent)
        else:
            break

    # fallback if empty
    if not selected:
        selected = sentences[:5]

    summary = "। ".join(selected).strip()

    # enforce minimum length
    if len(summary) < TARGET_MIN and len(sentences) > len(selected):
        for s in sentences[len(selected):]:
            summary += "। " + s
            if len(summary) >= TARGET_MIN:
                break

    # hard cap
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
            "keywords": keywords.strip()
        })

    return home()


@app.route("/delete_source/<int:index>")
def delete_source(index):
    if 0 <= index < len(SAVED_SOURCES):
        SAVED_SOURCES.pop(index)
    return home()


@app.route("/fetch_news")
def fetch_news():
    global LAST_FETCHED_NEWS
    LAST_FETCHED_NEWS = []

    for src in SAVAVED_SOURCES:
        feed = feedparser.parse(src["url"])
        keywords = [k.strip() for k in src["keywords"].split(",") if k.strip()]

        for entry in feed.entries[:20]:
            title = clean_text(entry.get("title", ""))
            summary = clean_text(entry.get("summary", ""))

            full_text = title + " " + summary

            if keywords:
                if not any(k in full_text for k in keywords):
                    continue

            LAST_FETCHED_NEWS.append({
                "title": title,
                "summary": summary[:400],
                "source": src["url"]
            })

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
