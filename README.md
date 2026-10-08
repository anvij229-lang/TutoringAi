# Studyroom - Track D MVP

A local-first prototype for Track D: Personalized Tutoring & Adaptive Learning. It covers course file upload, source-linked extraction for PDF pages, PPTX slides, and transcript cues, plus a tutor view that retrieves matching passages and cites the original source location. It can build glossary-based quizzes, score multiple-choice and short answers, update per-term mastery, and show quiz history.

## Run locally

Use Python 3.10 or newer.

```powershell
python -m pip install -r requirements.txt
python server.py
```

Open <http://127.0.0.1:8000>. If port 8000 is already occupied by another process, set `$env:PORT=8001` in PowerShell before running the app, then open <http://127.0.0.1:8001>. Uploaded files and the source index are stored in `data/` on this device. Remove that folder to clear the demo library.

Supported input: PDF, PPTX, TXT, VTT, and SRT; maximum 25 MB per file. A lecture video can be represented by its VTT/SRT transcript. Each extracted unit keeps its page, slide, or available transcript cue timestamps. The tutor uses transparent lexical matching and returns source excerpts rather than generating a paraphrase; unsupported questions receive a clear not-found response. The current topic tagger is a starter heuristic.

## Current API

- `GET /api/health`
- `GET /api/sources`
- `POST /api/sources` with a multipart `file`
- `POST /api/chat` with JSON `{ "question": "..." }`
- `GET /api/quiz/topics`
- `POST /api/quizzes` with a topic, difficulty, and question count
- `POST /api/quizzes/{quiz_id}/submit` with answers
- `GET /api/dashboard`
- `GET /api/sources/{source_id}/file` to open or download an original source
- `DELETE /api/sources/{source_id}`

## Planned slices

1. Improve extraction of figures and diagrams, and support direct video transcription.
2. Add a small evaluation set for citation accuracy, unsupported questions, and simulated learner profiles.
