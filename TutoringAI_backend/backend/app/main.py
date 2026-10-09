import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from app.routes import health, materials, tutor, quiz

app = FastAPI(title="TutoringAI API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("CORS_ORIGIN", "http://localhost:5173")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(materials.router)
app.include_router(tutor.router)
app.include_router(quiz.router)

@app.get("/")
def root():
    return {"name": "TutoringAI API", "status": "running"}