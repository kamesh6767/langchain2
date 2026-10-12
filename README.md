# 🧠 DocuMind — Local RAG AI Workspace

A self-hosted, containerized Document AI & RAG Assistant built with **FastAPI**, **LangChain**, and **ChromaDB**. 

Users can clone this repository, run a single command in their terminal, and immediately interact with an AI assistant in their browser. All documents, vector embeddings, and API keys are stored locally and persisted securely in a Docker volume.

---

## ⚡ Quick Start (One Command)

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running.
- [Git](https://git-scm.com/) installed.

### 1. Clone & Launch in Command Prompt / Terminal

Paste this command into your **Command Prompt**, **PowerShell**, or **Bash**:

```bash
git clone https://github.com/<your-username>/langchain2.git && cd langchain2 && docker compose up -d --build
```

*(On Windows, you can also just double-click `run.bat`)*

### 2. Open the App in Your Browser
Once the container starts, open:
👉 **[http://localhost:8000](http://localhost:8000)**

---

## 🔑 Configuring API Keys (Two Options)

DocuMind supports two convenient ways to configure your API keys for both **LLM** models and **Embedding** models:

### Option A: Directly Inside the Web App (Recommended)
1. Open the app at `http://localhost:8000`.
2. Click the **⚙️ Settings** icon in the top right header.
3. Paste your API key:
   - **OpenAI API Key** (`gpt-4o`, `gpt-4o-mini`, etc.)
   - **Google Gemini API Key** (`gemini-1.5-flash`, `gemini-1.5-pro`, etc.)
   - **Anthropic Claude API Key** (`claude-3-5-sonnet`, etc.)
   - **Groq API Key** (`llama-3.1-8b-instant`, etc.)
4. Click **Test** to verify connection, then click **Save Settings**.
   - *Your keys are saved to a persistent Docker volume (`./data/config/settings.json`) and won't be lost when you stop or restart the container.*

### Option B: Via `.env` File
Create a `.env` file before launching Docker:
```bash
cp .env.example .env
```
Open `.env` and fill in your keys:
```env
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AIzaSy...
ANTHROPIC_API_KEY=sk-ant-...
GROQ_API_KEY=gsk_...
```

---

## 🚀 Key Features

- **YouTube Video Transcripts:** Paste any YouTube link (watch link, shortened `youtu.be`, or embed) to fetch and embed timestamped transcripts into vector memory.
- **🛡️ Strict AI Guardrails:** Built-in domain guardrail policy that strictly refuses any query outside the scope of the provided YouTube video or uploaded documents, preventing hallucinations and off-topic conversations.
- **Document Q&A (RAG):** Drag and drop your **PDFs**, **DOCX**, **TXT**, **Markdown**, or **CSV** files into the sidebar.
- **Persistent Vector Storage:** Powered by **ChromaDB**. Document embeddings are saved in `./data/chroma/` and preserved across container restarts.
- **Multi-Provider LLM & Embeddings:**
  - **LLMs:** OpenAI (`gpt-4o-mini`), Google Gemini (`gemini-1.5-flash`), Anthropic Claude (`claude-3-5-sonnet`), and Groq (`llama-3.1`).
  - **Embeddings:** OpenAI (`text-embedding-3-small`), Google Gemini (`embedding-001`), or **HuggingFace (`all-MiniLM-L6-v2`)** which runs completely on local CPU with zero API costs!
- **Real-Time Streaming with Source Citations:** Streams token-by-token responses and displays expandable citation cards showing the source file and chunk preview.
- **Glassmorphic Dark UI:** Modern, responsive interface with fast zero-build static asset delivery.

---

## 🧪 Testing Locally Before Pushing to GitHub

Before pushing your changes to GitHub, test your setup locally using the following steps:

### 1. Run the Automated Test Suite
Run the included test runner to verify API endpoints, YouTube link parsing, and Guardrail behavior:
```bash
python test_app.py
```
*(All tests should complete with `OK`.)*

### 2. Test the Live Web UI
Run the local development server:
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser:
1. Paste a YouTube link into the sidebar (e.g., `https://www.youtube.com/watch?v=...`) and click **Add**.
2. Configure your API key in **Settings (Gear icon)**.
3. Ask a question about the video (e.g., *"Summarize the video"*).
4. Ask an unrelated question (e.g., *"What is the capital of Australia?"*) to verify the **Guardrails Notice** strictly refuses off-topic questions.

### 3. Test Docker Build & Containerization
Verify that the container builds and runs properly in Docker:
```bash
docker compose up -d --build
```
Check status:
```bash
docker compose ps
docker compose logs -f
```
Once verified, stop the container:
```bash
docker compose down
```

---

## 🛑 Stopping & Managing the Container

To stop the app:
```bash
docker compose down
```

To view container logs:
```bash
docker compose logs -f
```

To restart the container:
```bash
docker compose up -d
```

---

## 📁 Repository Structure

```
├── Dockerfile              # Docker container definition (Python 3.11-slim)
├── docker-compose.yml      # Persistent volume bindings and port routing
├── requirements.txt        # FastAPI, LangChain, ChromaDB dependencies
├── run.bat                 # Windows one-click launcher
├── run.sh                  # macOS/Linux launcher
├── .env.example            # Environment variables template
├── app/
│   ├── main.py             # FastAPI entrypoint & router aggregation
│   ├── config.py           # In-app settings & .env persistence manager
│   ├── core/
│   │   ├── model_factory.py# LLM & Embedding provider loader
│   │   ├── vector_store.py # ChromaDB index & persistence manager
│   │   └── rag_engine.py   # Document chunking & SSE streaming chat
│   ├── api/
│   │   ├── routes_chat.py  # Streaming chat endpoint
│   │   ├── routes_docs.py  # Upload, index, and delete documents
│   │   └── routes_config.py# API key status, update, and test endpoints
│   └── static/             # Frontend UI (HTML, CSS, JS)
└── data/                   # Persistent storage mounted in Docker (gitignored)
    ├── chroma/             # Vector database files
    ├── uploads/            # Uploaded documents
    └── config/             # User settings & stored keys
```

---

## 📄 License
MIT License. Feel free to fork, customize, and deploy!
