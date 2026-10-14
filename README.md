# Studyroom

Studyroom is a course study companion. Upload course PDFs, PowerPoint slides, or lecture videos, then study with source-grounded tutor answers, quizzes, flashcards, topic maps, and progress views.

## Prerequisites

- Git
- Python 3.10 or newer
- A PostgreSQL database URL (the project has been configured to use Supabase PostgreSQL)
- An LLM API key and compatible API endpoint/model for tutor and study-generation features
- FFmpeg and FFprobe on `PATH` to process video uploads

The frontend is plain HTML, CSS, and JavaScript; it does not need Node.js or a separate package install.

## Get the source

Clone the public repository and enter its project directory:

```bash
git clone https://github.com/anvij229-lang/TutoringAi.git
cd TutoringAi
```

## Configure the backend

Create a `.env` file inside `TutoringAI_backend/backend/`. Set the values for your own database and LLM provider. Keep this file private and never commit real credentials.

```dotenv
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DATABASE
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
UPLOAD_DIR=uploads
CORS_ORIGIN=http://localhost:5173

LLM_API_KEY=replace-with-your-api-key
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=replace-with-a-supported-model
SIMILARITY_THRESHOLD=0.24
```

Install FFmpeg separately. On Windows, for example, use `winget install --id Gyan.FFmpeg -e`, then open a new terminal and confirm `ffmpeg -version` and `ffprobe -version` work. On macOS, install FFmpeg with your package manager (for example, `brew install ffmpeg`).

Create a Python virtual environment, install backend requirements, and start FastAPI.

**Windows PowerShell** (run from the project root):

```powershell
cd TutoringAI_backend\backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8001
```

**macOS/Linux** (run from the project root):

```bash
cd TutoringAI_backend/backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8001
```

The API is available at <http://127.0.0.1:8001>; its interactive API documentation is at <http://127.0.0.1:8001/docs>.

## Run the frontend

Open a second terminal at the project root (the directory containing `web/`) and start the static file server:

**Windows PowerShell**

```powershell
py -m http.server 5173
```

**macOS/Linux**

```bash
python3 -m http.server 5173
```

Open <http://localhost:5173/web/>. Keep both the frontend server and FastAPI backend running while using the app. The browser frontend calls the backend at `http://127.0.0.1:8001`.

## Supported uploads

PDF, PPTX, MP4, MOV, MKV, WEBM, and M4V. Video processing requires FFmpeg/FFprobe and the configured transcription provider. Upload processing stores files under the backend's configured `UPLOAD_DIR`.

## Troubleshooting

- **Could not reach the backend:** make sure the FastAPI terminal is running on port `8001` and the frontend is open at `http://localhost:5173/web/`.
- **Missing configuration:** check that `TutoringAI_backend/backend/.env` exists and contains valid database and LLM settings.
- **FFmpeg is not installed:** install FFmpeg/FFprobe, open a new terminal, verify both commands work, then restart FastAPI.
- **Python package/import errors:** activate the backend virtual environment and install `requirements.txt` again.

## Security

Never commit `.env` files, database passwords, or API keys. Each developer should configure their own local `.env` using credentials shared through a secure channel.
