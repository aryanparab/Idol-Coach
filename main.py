from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from song import router as song_router
from user import router as user_router


#uvicorn main:app --reload
app = FastAPI()

# CORS for frontend connection (adjust origin for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # or frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(song_router, prefix="/songs", tags=["Songs"])
app.include_router(user_router, prefix="/user", tags=["User"])
