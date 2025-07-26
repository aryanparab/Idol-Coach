# Idol Singing Coach

An AI-powered singing assistant that helps users improve their vocals using intelligent feedback, karaoke-style interaction, and lyric synchronization. The app features song processing from YouTube, lyric-vocal alignment using Gentle API, and a conversational coaching interface.

---

## 🌐 Live Preview (Local Development)
https://drive.google.com/file/d/1lrmUADXCLoX4zMPax3VONWv4kNPECEs1/view?usp=sharing
**Run the following in separate terminals:**

### 1. **Start FastAPI Backend**

```bash
uvicorn main:app --reload
```

### 2. **Run Gentle API (for lyric alignment)**

Ensure Docker is running, then run:

```bash
docker run -p 8765:8765 lowerquality/gentle
```

### 3. **Start Frontend (Next.js)**

```bash
cd idol-singing-coach-frontend
npm install
npm run dev
```

---

## 🔧 Features

- Google Login using NextAuth
- Search and download any song from YouTube
- Automatically extracts:
  - Lyrics using Genius API
  - Vocals & accompaniment
  - Lyric-vocal alignment via Gentle API
- AI chat coaching on user-sung audio
- Mini karaoke mode: view synced lyrics + listen to original
- Sidebar with chat history per song

---

## 🌐 Folder Structure

```
project-root/
├── main.py                  # FastAPI app entry point
├── .env                    # Environment variables (see below)
├── mongo.py                # MongoDB utilities
├── s3_handler.py           # S3 vs local switch handler
├── user.py                 # User audio handling & feedback
├── song.py                 # Song processing logic
├── coaching.py             # Song preparation logic
├── process_user_audio.py   # Audio analysis pipeline
├── scripts/                # Download and preparation scripts
├── scripts_user/           # User singing comparison & feedback
├── songs/                  # Stores processed songs (vocals, lyrics, etc.)
├── idol-singing-coach-frontend/
│   └── .env.local          # Frontend env vars
│   └── src/                # React + Next.js app
├── test_codes/             # (Ignore - for testing)
```

---

## 📁 .env (Backend)

Create a `.env` file in root:

```env
GENIUS_CLIENT_ID=
GENIUS_CLIENT_SECRET=
GENIUS_API_KEY=
GEMINI_API_KEY=
NEXT_PUBLIC_API_BASE_URL="http://localhost:8000"
MONGODB_URI=
MONGODB_DB=idol-coach
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-2
S3_BUCKET_NAME=idol-singing-coach
PRODUCTION="false"  # set to true to enable S3 + MongoDB in production
```

---

## 📁 .env.local (Frontend)

Inside `idol-singing-coach-frontend/`, create `.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=
MONGODB_URI=
MONGODB_DB=idol-coach
NODE_ENV="development"
```

---

## 🚀 How It Works

1. **User logs in** via Google OAuth.
2. **Searches for a song** via YouTube URL or keyword.
3. System:
   - Downloads song
   - Fetches lyrics using Genius
   - Separates vocals and accompaniment
   - Aligns lyrics to vocals using Gentle API (via Docker)
4. Once processing is complete (can take \~4 minutes), chat window opens.
5. User can:
   - Sing parts of the song and receive feedback
   - View synced lyrics and original audio in karaoke mode
   - Revisit previous feedback chats in sidebar

---

## 🤖 Technologies Used

- **Frontend:** React, Next.js, TailwindCSS, NextAuth
- **Backend:** FastAPI, Python, Uvicorn
- **Storage & APIs:**
  - YouTube (yt-dlp)
  - Genius API (lyrics)
  - Gentle (Docker container)
  - AWS S3 (optional)
  - MongoDB (chat + song storage)

---

## 🚧 Setup Notes

- Song processing takes \~4 minutes; use logs for status.
- Gentle API **must** be running before song alignment.
- Ensure `.env` and `.env.local` files are properly configured.
- `PRODUCTION=true` enables AWS S3 + MongoDB for cloud storage.

---

## 📆 Future Enhancements

- Real-time pitch and rhythm analysis
- Leaderboard or scoring system
- Mobile responsive UI
- Song segmentation or feedback loops

---

## ✨ Contributing

PRs welcome! Make sure to clearly document changes.

---

## 🙏 Acknowledgements

- [Gentle Forced Aligner](https://lowerquality.com/gentle/)
- Genius API for lyrics
- Google OAuth via NextAuth

