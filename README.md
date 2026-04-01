# 📄 AI Research Paper Summarizer

AI-powered web app that summarizes research papers (PDFs) into structured and readable insights using LLMs.

---

## 🚀 Features

* Upload PDF research papers
* Generates structured summaries
* Covers key ideas, methods, and results
* Handles large documents using chunking
* Clean and responsive UI

---

## 📸 Screenshots

### 🏠 Home Page

<img src="Research Paper Summarizer/images/Home.png" width="700"/>

### 📊 Summary Output

<img src="Research Paper Summarizer/images/result.png" width="700"/>

---

## 🛠️ Tech Stack

* Python (Flask)
* HTML, CSS, JavaScript
* LangChain
* Groq API (LLaMA 3.1)
* pdfplumber

---

## 📁 Project Structure

```
research_summarizer/
│
├── app.py
├── utils.py
├── requirements.txt
├── README.md
│
├── templates/
│   └── index.html
│
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── script.js
│
├── images/
│   ├── home.png
│   └── result.png
```

---

## ⚙️ Setup Instructions

### 1. Clone the repository

```
git clone <your-repo-link>
cd research_summarizer
```

### 2. Install dependencies

```
pip install -r requirements.txt
```

### 3. Create `.env` file

```
GROQ_API_KEY=your_api_key_here
```

### 4. Run the application

```
python app.py
```

Open in browser:
http://127.0.0.1:5000

---

## ⚠️ Important Notes

* Do NOT upload `.env` file
* Requires a valid Groq API key
* Best works with Python 3.9–3.12

---

## 📌 Future Improvements

* Download summary as PDF
* Add loading/progress indicator
* Deploy online

---

## 👨‍💻 Author

Student project for research paper summarization.
