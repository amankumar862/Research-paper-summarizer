from flask import Flask, request, jsonify, render_template
import os
import uuid
import threading
import time
import requests
from dotenv import load_dotenv

from langchain_community.document_loaders import PyPDFLoader
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter

from google import genai

load_dotenv()

# =========================
# Multi API Setup
# =========================

gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

groq_llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0.3,
    max_tokens=4096
)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# =========================
# Flask App
# =========================

app = Flask(__name__)
jobs = {}

RETRY_LIMIT = 4

# =========================
# LLM Callers
# =========================

def call_gemini(messages):
    try:
        print("\n[TRY] Gemini 2.5 Flash")

        prompt = "\n".join([m.content for m in messages])

        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        print("[SUCCESS] Gemini 2.5\n")
        return response.text

    except Exception as e:
        print("[FAIL] Gemini:", e)
        return None


def call_groq(messages):
    try:
        print("[TRY] Groq LLaMA")

        result = groq_llm.invoke(messages).content

        print("[SUCCESS] Groq\n")
        return result

    except Exception as e:
        print("[FAIL] Groq:", e)
        return None


def call_openrouter(messages):
    try:
        print("[TRY] OpenRouter LLaMA")

        prompt = "\n".join([m.content for m in messages])

        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:5000",
                "X-Title": "Research Summarizer"
            },
            json={
                "model": "meta-llama/llama-3-8b-instruct",
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
        )

        data = response.json()

        # ✅ FIXED SAFE PARSING
        if "choices" in data:
            result = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            print("[SUCCESS] OpenRouter\n")
            return result
        else:
            print("[FAIL] OpenRouter Response Error:", data)
            return None

    except Exception as e:
        print("[FAIL] OpenRouter Exception:", e)
        return None



# =========================
# Retry Logic
# =========================

def retry_with_backoff(messages):
    for attempt in range(RETRY_LIMIT):
        print(f"\n--- Attempt {attempt+1} ---")

        res = call_gemini(messages)
        if res and res.strip():
            return res
        print("➡️ Switching to OpenRouter...")

        res = call_openrouter(messages)
        if res and res.strip():
            return res
        print("➡️ Switching to Groq...")

        res = call_groq(messages)
        if res and res.strip():
            return res

        print("⏳ Retrying after backoff...\n")
        time.sleep(1.5 ** attempt)

    return "Summary unavailable due to API issue."


# =========================
# 🔥 FIX: TABLE CLEANER
# =========================

def fix_table_format(text):
    lines = text.split("\n")
    clean_lines = []

    for line in lines:
        # Remove broken inline rows
        if "|" in line and line.count("|") > 4 and "||" in line:
            continue

        clean_lines.append(line)

    return "\n".join(clean_lines)


# =========================
# Key Points Table (FIXED PROMPT)
# =========================

def extract_key_points(text):
    messages = [
        SystemMessage(content="""
Return ONLY a VALID Markdown table.

STRICT RULES:
- Use EXACTLY 2 columns: Aspect | Details
- Each row MUST be on a new line
- DO NOT merge multiple rows in one line
- DO NOT add extra text before or after table
- DO NOT write inline table
- DO NOT break rows

FORMAT:

| Aspect | Details |
|--------|--------|
| Author & Year | ... |
| Methodology | ... |
| Highlights / Performance | ... |
| Observations / Limitations | ... |
"""),
        HumanMessage(content=text[:12000])
    ]

    return retry_with_backoff(messages)





# =========================
# Title & Authors
# =========================

def extract_title_authors(text):
    messages = [
        SystemMessage(content="Extract only Title and Authors.\nFormat:\nTitle: ...\nAuthors: ..."),
        HumanMessage(content=text[:3000])
    ]

    result = retry_with_backoff(messages)

    title = "Unknown Title"
    authors = "Unknown Authors"

    for line in result.split("\n"):
        if "Title:" in line:
            title = line.split(":", 1)[1].strip()
        elif "Authors:" in line:
            authors = line.split(":", 1)[1].strip()

    return title, authors


# =========================
# Summary Functions
# =========================

def short_summary(pages, job_id):
    jobs[job_id]["progress"] = 15

    full_text = "\n".join(pages[:40])
    jobs[job_id]["progress"] = 40

    messages = [
        SystemMessage(content="""
Return STRICTLY in this format:

| Aspect | Details |
|--------|--------|
| Author & Year | |
| Methodology | |
| Highlights / Performance | |
| Observations / Limitations | |

IMPORTANT:
- DO NOT write inline table
- DO NOT break rows
- Keep proper markdown formatting

Then:

**Short Summary:**
4-6 sentence summary.
"""),
        HumanMessage(content=full_text[:12000])
    ]

    result = retry_with_backoff(messages)
    result = fix_table_format(result)

    jobs[job_id]["progress"] = 90
    return result


def medium_summary(pages, job_id):
    jobs[job_id]["progress"] = 15

    text = "\n".join(pages[:30])
    key_table = fix_table_format(extract_key_points(text))

    splitter = RecursiveCharacterTextSplitter(chunk_size=2500, chunk_overlap=200)
    chunks = splitter.split_text(text)[:6]

    summaries = []

    for chunk in chunks:
        messages = [
            SystemMessage(content="Summarize this section clearly."),
            HumanMessage(content=chunk)
        ]

        summaries.append(retry_with_backoff(messages))
        jobs[job_id]["progress"] += 12

    combined = "\n\n".join(summaries)

    merge_messages = [
        SystemMessage(content="Merge into structured medium summary."),
        HumanMessage(content=combined)
    ]

    summary = retry_with_backoff(merge_messages)

    jobs[job_id]["progress"] = 92
    return f"{key_table}\n\n**Medium Summary:**\n{summary}"


def large_summary(pages, job_id):
    jobs[job_id]["progress"] = 10

    text = "\n".join(pages)
    key_table = fix_table_format(extract_key_points(text))

    splitter = RecursiveCharacterTextSplitter(chunk_size=2500, chunk_overlap=300)
    chunks = splitter.split_text(text)[:10]

    summaries = []

    for chunk in chunks:
        messages = [
            SystemMessage(content="Give detailed summary with technical numbers."),
            HumanMessage(content=chunk)
        ]

        summaries.append(retry_with_backoff(messages))
        jobs[job_id]["progress"] += int(65 / len(chunks))

    combined = "\n\n".join(summaries)

    merge_messages = [
        SystemMessage(content="Create a long detailed summary."),
        HumanMessage(content=combined)
    ]

    summary = retry_with_backoff(merge_messages)

    jobs[job_id]["progress"] = 95
    return f"{key_table}\n\n**Large Detailed Summary:**\n{summary}"


# =========================
# Routes
# =========================

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/summarize", methods=["POST"])
def summarize():
    file = request.files["file"]
    length = request.form.get("length", "medium")

    file_path = f"./temp_{uuid.uuid4().hex}.pdf"
    file.save(file_path)

    job_id = str(uuid.uuid4())
    jobs[job_id] = {"progress": 5, "summary": ""}

    def run():
        try:
            loader = PyPDFLoader(file_path)
            docs = loader.load()
            pages = [d.page_content for d in docs]

            title, authors = extract_title_authors(pages[0] if pages else "")

            if length == "short":
                final = short_summary(pages, job_id)
            elif length == "medium":
                final = medium_summary(pages, job_id)
            else:
                final = large_summary(pages, job_id)

            final = f"# {title}\n\n**Authors:** {authors}\n\n{final}"

            jobs[job_id]["summary"] = final
            jobs[job_id]["progress"] = 100

        except Exception as e:
            jobs[job_id]["summary"] = f"Error: {str(e)}"
            jobs[job_id]["progress"] = 100

        finally:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass

    threading.Thread(target=run, daemon=True).start()

    return jsonify({"job_id": job_id})


@app.route("/progress/<job_id>")
def progress(job_id):
    return jsonify(jobs.get(job_id, {"progress": 0, "summary": ""}))


if __name__ == "__main__":
    app.run(debug=True)