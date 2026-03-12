import json
import os
import shutil
import time
from urllib.parse import quote
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from mongo import MongoHandler, get_all_songs, get_song, insert_song
from s3_handler import storage

load_dotenv()

router = APIRouter()

# ── Local song cache config ────────────────────────────────────────────────────
SONGS_DIR = "songs"
MAX_CACHED_SONGS = 3
CACHE_MANIFEST_PATH = "cache_manifest.json"   # lives at repo root, NOT inside songs/


def _load_manifest() -> dict:
    if os.path.exists(CACHE_MANIFEST_PATH):
        try:
            with open(CACHE_MANIFEST_PATH, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"⚠️  Corrupt cache manifest — resetting: {e}")
    return {}


def _save_manifest(manifest: dict):
    with open(CACHE_MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)


def _song_is_cached(song_name: str) -> bool:
    """True only if both core audio files are present locally."""
    song_dir = os.path.join(SONGS_DIR, song_name)
    return (
        os.path.exists(os.path.join(song_dir, "vocals.wav")) and
        os.path.exists(os.path.join(song_dir, "accompaniment.wav"))
    )


def _evict_lru_if_needed(manifest: dict, current_song: str) -> dict:
    """If cache already holds MAX_CACHED_SONGS OTHER songs, evict the least-recently-used one."""
    others = {k: v for k, v in manifest.items() if k != current_song}
    if len(others) >= MAX_CACHED_SONGS:
        lru = min(others, key=lambda k: others[k].get("last_accessed", 0))
        print(f"🗑️  Cache full — evicting LRU song: {lru}")
        song_dir = os.path.join(SONGS_DIR, lru)
        if os.path.exists(song_dir):
            shutil.rmtree(song_dir)
        del manifest[lru]
    return manifest


def _download_song_from_s3(song_name: str, song_data: dict):
    """Download all relevant song files from S3 into the local songs directory."""
    song_dir = os.path.join(SONGS_DIR, song_name)
    os.makedirs(song_dir, exist_ok=True)

    # Core audio files — prefer the paths stored in MongoDB, fall back to convention.
    vocals_key = song_data.get("vocals_path") or f"songs/{song_name}/vocals.wav"
    accomp_key = (
        song_data.get("accompaniment_path") or f"songs/{song_name}/accompaniment.wav"
    )

    files_to_fetch = {
        "vocals.wav":        vocals_key,
        "accompaniment.wav": accomp_key,
    }

    # Lyrics text file — path stored in MongoDB
    if song_data.get("lyrics"):
        key = song_data["lyrics"]
        files_to_fetch[os.path.basename(key)] = key

    # Alignment / timestamp lyrics
    if song_data.get("timestamp_lyrics"):
        key = song_data["timestamp_lyrics"]
        files_to_fetch[os.path.basename(key)] = key

    for local_name, s3_key in files_to_fetch.items():
        local_path = os.path.join(song_dir, local_name)
        if os.path.exists(local_path):
            continue                          # already downloaded
        try:
            print(f"⬇️  Downloading s3://{s3_key} …")
            data = storage.read_file(s3_key, mode="rb")
            with open(local_path, "wb") as f:
                f.write(data if isinstance(data, bytes) else data.encode())
            print(f"✅  Saved: {local_name}")
        except Exception as e:
            print(f"⚠️  Could not download {s3_key}: {e}")


def _ensure_song_cached(song_name: str, song_data: dict):
    """
    Guarantee that song files are in the local cache.
    Downloads from S3 if missing, evicts LRU if cache is full.
    Always updates the last-accessed timestamp.
    """
    manifest = _load_manifest()

    if not _song_is_cached(song_name):
        print(f"📥 Song not cached locally — fetching from S3: {song_name}")
        manifest = _evict_lru_if_needed(manifest, song_name)
        _download_song_from_s3(song_name, song_data)
    else:
        print(f"✅ Song already in local cache: {song_name}")

    manifest[song_name] = {"last_accessed": time.time()}
    _save_manifest(manifest)


def _read_song_files_from_local(song_name: str) -> tuple[str, str]:
    """Read lyrics text and alignment JSON from local song directory."""
    song_dir = os.path.join(SONGS_DIR, song_name)
    lyrics = ""
    timestamp_lyrics = ""

    if not os.path.exists(song_dir):
        return lyrics, timestamp_lyrics

    for fname in os.listdir(song_dir):
        if fname.endswith(".txt"):
            with open(os.path.join(song_dir, fname), "r", encoding="utf-8") as f:
                lyrics = f.read()
        elif fname == "alignment.json":
            with open(os.path.join(song_dir, fname), "r", encoding="utf-8") as f:
                timestamp_lyrics = f.read()

    return lyrics, timestamp_lyrics


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("/list")
def get_all_songs_endpoint():
    """Get all songs from the database."""
    try:
        songs = get_all_songs()
        return {"songs": songs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching songs: {e}")


class SongRequest(BaseModel):
    song_name: str


@router.post("/prepare")
def prepare_song(req: SongRequest):
    """Prepare a song — check if it exists in DB; if not, process it via coaching()."""
    song_name = req.song_name.strip().lower()

    try:
        with MongoHandler() as handler:
            song = handler.get_song_by_normalized_title(handler.normalize_text(song_name))
            if song:
                return {"message": "Song already prepared", "song_data": song}

            print("Song not in DB — running coaching()")
            from coaching import coaching

            try:
                song_data = coaching(song_name)
                song_data["normalized_title"] = handler.normalize_text(song_data["title"])

                success = handler.insert_song(song_data)
                if not success:
                    raise HTTPException(status_code=500, detail="Failed to save song to database")

                song_data.pop("_id", None)
                return {"message": "Song prepared successfully", "song_data": song_data}

            except Exception as e:
                print(e)
                raise HTTPException(status_code=500, detail=f"Error preparing song: {e}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@router.post("/get_song")
def getSong(req: SongRequest):
    """
    Return lyrics, alignment data, and audio URLs for a song.

    In production mode:
      - Downloads the song from S3 into a local cache (max 3 songs, LRU eviction)
        if it is not already cached.
      - Serves audio via the /audio static-file route on this backend.

    In local mode:
      - Reads directly from the local songs/ directory (existing behaviour).
    """
    try:
        song = get_song(req.song_name)
        if not song:
            raise HTTPException(
                status_code=404,
                detail=f"Song not found in database: {req.song_name}"
            )

        # Use the canonical title from MongoDB for all local-cache operations.
        # req.song_name may be a partial/fuzzy match; song["title"] is the ground truth.
        canonical_name = song.get("title", req.song_name)

        if storage.is_production:
            # Ensure the song's files are present in the local cache.
            # Non-fatal: if S3 download fails we still try to serve whatever is local.
            try:
                _ensure_song_cached(canonical_name, song)
            except Exception as e:
                print(f"⚠️  Cache/S3 operation failed (will try local anyway): {e}")

        # Read lyrics / alignment from local disk (same for both modes)
        lyrics, timestamp_lyrics = _read_song_files_from_local(canonical_name)

        # Build audio URLs — served via the /audio static-file mount in main.py
        backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
        song_url = quote(canonical_name)          # handles spaces and special chars
        f1 = f"{backend_url}/audio/{song_url}/vocals.wav"
        f2 = f"{backend_url}/audio/{song_url}/accompaniment.wav"

        return {
            "lyrics": lyrics,
            "timestamp_lyrics": timestamp_lyrics,
            "audio_urls": [f1, f2],
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting song files: {e}")


if __name__ == "__main__":
    # One-time utility: seed MongoDB from the local JSON backup
    try:
        with MongoHandler() as handler:
            success = handler.load_songs_from_json("songs/songs_db.json")
            print("Songs loaded!" if success else "Failed to load songs.")
    except Exception as e:
        print(f"Error loading songs: {e}")
