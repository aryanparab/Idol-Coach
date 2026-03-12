import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from song import router as song_router
from user import router as user_router

load_dotenv()

# uvicorn main:app --reload
app = FastAPI()

# ── CORS ───────────────────────────────────────────────────────────────────────
# Add origins via FRONTEND_URL env var for production; localhost:3000 always allowed.
_frontend_url = os.getenv("FRONTEND_URL", "")
origins = list(filter(None, ["http://localhost:3000", _frontend_url]))

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API routes ─────────────────────────────────────────────────────────────────
app.include_router(song_router, prefix="/songs", tags=["Songs"])
app.include_router(user_router, prefix="/user", tags=["User"])

# ── Static audio files ─────────────────────────────────────────────────────────
# Served at /audio/<song_name>/vocals.wav  etc.
# Using /audio instead of /songs to avoid prefix collision with the songs router.
os.makedirs("songs", exist_ok=True)
app.mount("/audio", StaticFiles(directory="songs"), name="audio")
