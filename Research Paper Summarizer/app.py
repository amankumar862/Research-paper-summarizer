from flask import Flask, render_template, request
from utils import pdf_to_text, chunk_text, summarize_chunks, combine_summaries
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)


@app.route("/", methods=["GET", "POST"])
def index():
    summary = ""

    if request.method == "POST":
        print("Request received")

        file = request.files.get("file")

        if file and file.filename.endswith(".pdf"):
            text = pdf_to_text(file)

            if text.strip():
                chunks = chunk_text(text)
                summaries = summarize_chunks(chunks)
                summary = combine_summaries(summaries)

    return render_template("index.html", summary=summary)


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)