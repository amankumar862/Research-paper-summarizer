from flask import Flask, request, jsonify, render_template
import os
import uuid
import threading
import time
import requests
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

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
    max_tokens=8192
)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# =========================
# Flask App
# =========================

app = Flask(__name__)
jobs = {}
# 🔥 Store PDF chunks for chat
pdf_store = {}

RETRY_LIMIT = 4

# =========================
# Embedding Model for Chat
# =========================

embed_model = SentenceTransformer("all-MiniLM-L6-v2")

vector_store = {}
chunk_store = {}

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
        if res and len(res.strip()) > 80:
            return res

        print("➡️ Switching to OpenRouter...")

        res = call_openrouter(messages)
        if res and len(res.strip()) > 80:
            return res
        print("➡️ Switching to Groq...")

        res = call_groq(messages)
        if res and len(res.strip()) > 80:
            return res

        print("⏳ Retrying after backoff...\n")
        time.sleep(1.5 ** attempt)

    return "Summary unavailable due to API issue."

# =========================
# TABLE CLEANER
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
# Key Points Table
# =========================

def extract_key_points(text):
    messages = [
        SystemMessage(content="""
Return ONLY a valid Markdown table.

STRICT RULES:
• Output ONLY the table.
• No explanation before or after.
• Exactly 4 rows.

| Aspect | Details |
|--------|--------|
| Author & Year | |
| Methodology | |
| Highlights / Performance | |
| Observations / Limitations | |
"""),
        HumanMessage(content=text[:12000])
    ]

    return retry_with_backoff(messages)

def detect_sections(text):
    sections = {}

    keywords = [
        "abstract",
        "introduction",
        "method",
        "methodology",
        "experiment",
        "results",
        "discussion",
        "conclusion"
    ]

    current_section = "general"
    sections[current_section] = []

    for line in text.split("\n"):

        lower = line.lower()

        for key in keywords:
            if key in lower and len(line) < 60:
                current_section = key
                sections[current_section] = []
                break

        sections.setdefault(current_section, []).append(line)

    return {k: "\n".join(v) for k, v in sections.items()}

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
        
    title = title.replace("*", "")
    authors = authors.replace("*", "")

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
Generate a SHORT research paper summary.

Rules:
- Write ONLY the summary.
- 5 to 7 sentences.
- Do NOT include title or authors.
- Do NOT use markdown symbols like ** or *.
- Do NOT add headings.
"""),
    HumanMessage(content=full_text[:12000])
]

    result = retry_with_backoff(messages)

    result = fix_table_format(result)

    # 🔥 remove markdown stars
    result = result.replace("**", "")
    result = result.replace("*", "")

    jobs[job_id]["progress"] = 90

    return result


def medium_summary(pages, job_id):
    jobs[job_id]["progress"] = 15

    text = "\n".join(pages[:30])
    sections = detect_sections(text)
    text = "\n\n".join(sections.values())
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
    SystemMessage(content="""
        Create a structured research paper summary.

        Use CLEAR section headings exactly like this:

        ## Introduction
        ## Architecture
        ## Methodology
        ## Results
        ## Applications
        ## Conclusion

        Rules:
        - Each section must start on a new line
        - Leave a blank line after every heading
        - Write 2–4 sentences per section
        """),
            HumanMessage(content=combined)
        ]

    summary = retry_with_backoff(merge_messages)

    jobs[job_id]["progress"] = 92

    summary = summary.replace("**", "")
    summary = summary.replace("*", "")
    return f"{key_table}\n\n{summary}"


def large_summary(pages, job_id):

    jobs[job_id]["progress"] = 10

    text = "\n".join(pages)

    # Key table
    key_table = fix_table_format(extract_key_points(text))

    # Split paper
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=2200,
        chunk_overlap=300
    )

    chunks = splitter.split_text(text)[:20]

    summaries = []

    # SECTION SUMMARIES
    for chunk in chunks:

        messages = [
            SystemMessage(content="""
You are summarizing a section of a research paper.

Requirements:
• Write a detailed explanation of the section.
• Explain the ideas, mechanisms, and concepts clearly.
• Mention datasets, experiments, numbers, and results if present.
• Expand technical concepts.

Length requirement:
Write between 250 and 350 words.

IMPORTANT:
Do NOT write a short summary.
"""),

            HumanMessage(content=chunk)
        ]

        part = retry_with_backoff(messages)

        if part:
            summaries.append(part)

        jobs[job_id]["progress"] += int(60 / len(chunks))

    combined = "\n\nSECTION ANALYSIS\n\n".join(summaries)

    # FINAL MERGE
    merge_messages = [

        SystemMessage(content="""
You are generating a VERY LARGE academic summary of a research paper.

STRICT LENGTH REQUIREMENT:
The final summary MUST be between 1800 and 2600 words.

You MUST expand the explanations and include detailed reasoning.

STRUCTURE THE SUMMARY USING THESE SECTIONS:

1. Background and Motivation
2. Problem Statement
3. Proposed Method / Model Architecture
4. Core Concepts and Mechanisms
5. Methodology and Training Process
6. Experiments and Evaluation Setup
7. Results and Performance Analysis
8. Observations and Insights
9. Limitations and Challenges
10. Real-world Applications
11. Future Research Directions
12. Final Conclusion

IMPORTANT RULES:
• Write detailed academic explanations.
• Expand technical ideas.
• Avoid short paragraphs.
• Each section should contain multiple paragraphs.
• Avoid Markdown symbols like ** or *.
"""),

        HumanMessage(content=combined)
    ]

    summary = retry_with_backoff(merge_messages)

    jobs[job_id]["progress"] = 95

    return f"{key_table}\n\n{summary}"

# =========================
# Routes
# =========================

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/app")
def app_ui():
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

            # 🔥 Save chunks for chat
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=1200,
                chunk_overlap=200
            )

            chunks = splitter.split_text("\n".join(pages))

            # Store chunks
            chunk_store[job_id] = chunks

            # Create embeddings
            embeddings = embed_model.encode(chunks)

            # Create FAISS index
            dimension = embeddings.shape[1]
            index = faiss.IndexFlatL2(dimension)
            index.add(np.array(embeddings).astype("float32"))

            vector_store[job_id] = index
            
            title, authors = extract_title_authors("\n".join(pages[:2]))
            authors = authors.replace("*", "")
            title = title.replace("*", "")

            if length == "short":
                final = short_summary(pages, job_id)
            elif length == "medium":
                final = medium_summary(pages, job_id)
            else:
                final = large_summary(pages, job_id)

            final = f"# {title}\n\n**Authors:** {authors}\n\n\n{final}"
            
            jobs[job_id]["summary"] = final
            jobs[job_id]["progress"] = 100

        except Exception as e:
            jobs[job_id]["summary"] = f"Error: {str(e)}"
            jobs[job_id]["progress"] = 100

        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

    threading.Thread(target=run, daemon=True).start()

    return jsonify({"job_id": job_id})


@app.route("/progress/<job_id>")
def progress(job_id):
    return jsonify(jobs.get(job_id, {"progress": 0, "summary": ""}))


# =========================
# CHAT WITH PDF
# =========================

@app.route("/chat/<job_id>", methods=["POST"])
def chat(job_id):

    question = request.json.get("question")

    if job_id not in vector_store:
        return jsonify({"answer": "PDF not available."})

    index = vector_store[job_id]
    chunks = chunk_store[job_id]

    # Embed the question
    query_embedding = embed_model.encode([question])

    # Search top relevant chunks
    D, I = index.search(np.array(query_embedding).astype("float32"), 5)

    relevant_chunks = [chunks[i] for i in I[0]]

    context = "\n\n".join(relevant_chunks)

    messages = [
        SystemMessage(content=f"""
Answer the question using the research paper context.

If the answer is not in the paper, say you cannot find it.

Paper context:
{context}
"""),
        HumanMessage(content=question)
    ]

    answer = retry_with_backoff(messages)

    return jsonify({"answer": answer})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)