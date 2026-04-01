import pdfplumber
import time
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()

llm = ChatGroq(model="llama-3.1-8b-instant")


# 🔹 Extract text from PDF
def pdf_to_text(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text


# 🔹 Chunking (slightly safer)
def chunk_text(text):
    chunks = []
    chunk_size = 2000   # 🔻 reduced from 2500

    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end

    return chunks


# 🔹 Summarize each chunk (SHORTER OUTPUT)
def summarize_chunks(chunks):
    summaries = []

    for i, chunk in enumerate(chunks):
        print(f"Processing chunk {i+1}/{len(chunks)}")

        result = llm.invoke([
            SystemMessage(content="""
Summarize this research text into concise bullet points.

Rules:
- Max 6–8 bullet points
- Keep only key ideas, methods, results
- No long explanations
"""),
            HumanMessage(content=chunk)
        ])

        summaries.append(result.content)
        time.sleep(0.6)   # 🔻 slightly increased delay

    return summaries


# 🔹 Combine summaries (SAFE)
def combine_summaries(summaries):

    while len(summaries) > 1:
        new_summaries = []

        for i in range(0, len(summaries), 2):
            group = summaries[i:i+2]
            combined_text = "\n".join(group)

            result = llm.invoke([
                SystemMessage(content="""
Combine into a detailed and well-structured final summary.

Rules:
- Expand the content clearly
- Cover all important points from input
- Explain concepts properly
- Keep it detailed (like 2–3 pages worth)
- Use sections if needed
"""),
                HumanMessage(content=combined_text[:3800])  # 🔻 reduced from 4000
            ])

            new_summaries.append(result.content)
            time.sleep(1.2)   # 🔻 more safe delay

        summaries = new_summaries
        print(f"Reduced to {len(summaries)} summaries")

    return summaries[0]