from flask import Flask, render_template_string, request

app = Flask(__name__)

# Simple in-memory storage (later we upgrade)
sources = []

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Runner News Dashboard</title>
    <style>
        body { font-family: Arial; padding: 20px; }
        input, textarea { width: 100%; padding: 8px; margin: 5px 0; }
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
        <li>{{s.url}} | Keywords: {{s.keywords}}</li>
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

@app.route("/")
def home():
    return render_template_string(HTML_PAGE, sources=sources, news=None)

@app.route("/add_source", methods=["POST"])
def add_source():
    url = request.form.get("url")
    keywords = request.form.get("keywords")

    sources.append({
        "url": url,
        "keywords": keywords
    })

    return render_template_string(HTML_PAGE, sources=sources, news=None)

@app.route("/fetch", methods=["POST"])
def fetch_news():
    # DEMO news (real scraping later)
    demo_news = {
        "heading": "বাংলাদেশে নতুন অর্থনৈতিক অগ্রগতি",
        "body": "বাংলাদেশের অর্থনীতি সাম্প্রতিক সময়ে উল্লেখযোগ্য উন্নতি অর্জন করেছে। বিভিন্ন খাতে প্রবৃদ্ধি বৃদ্ধি পেয়েছে এবং বিশেষজ্ঞরা আশা করছেন এই ধারা অব্যাহত থাকবে।"
    }

    return render_template_string(HTML_PAGE, sources=sources, news=demo_news)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
