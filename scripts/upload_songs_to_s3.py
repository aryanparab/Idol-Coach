"""
upload_songs_to_s3.py
─────────────────────
One-time migration script: uploads all locally-processed song files to S3
and updates MongoDB records so that `lyrics` and `timestamp_lyrics` fields
contain the correct S3 key paths.

Run from the repo root:
    python scripts/upload_songs_to_s3.py

Requirements: PRODUCTION=true (or any value) in .env with valid AWS creds.
"""

import os
import sys
import json
from pathlib import Path

# ── make repo root importable ──────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from mongo import MongoHandler

# ── config ─────────────────────────────────────────────────────────────────────
SONGS_DIR  = "songs"
BUCKET     = os.getenv("S3_BUCKET_NAME", "idol-singing-coach")
REGION     = os.getenv("AWS_REGION", "us-east-2")

s3 = boto3.client(
    "s3",
    config=Config(signature_version="s3v4"),
    region_name=REGION,
)

CONTENT_TYPES = {
    ".wav":  "audio/wav",
    ".mp3":  "audio/mpeg",
    ".json": "application/json",
    ".txt":  "text/plain; charset=utf-8",
    ".srt":  "text/plain; charset=utf-8",
}


def object_exists(key: str) -> bool:
    try:
        s3.head_object(Bucket=BUCKET, Key=key)
        return True
    except ClientError:
        return False


def upload_file(local_path: str, s3_key: str) -> bool:
    ext = Path(local_path).suffix.lower()
    content_type = CONTENT_TYPES.get(ext, "application/octet-stream")
    try:
        s3.upload_file(
            local_path, BUCKET, s3_key,
            ExtraArgs={"ContentType": content_type},
        )
        print(f"  ✅ uploaded → s3://{BUCKET}/{s3_key}")
        return True
    except Exception as e:
        print(f"  ❌ failed  → {s3_key}: {e}")
        return False


def main():
    if not os.path.isdir(SONGS_DIR):
        print(f"❌ '{SONGS_DIR}' directory not found. Run from repo root.")
        sys.exit(1)

    song_dirs = [
        d for d in Path(SONGS_DIR).iterdir()
        if d.is_dir() and not d.name.startswith(".")
    ]

    if not song_dirs:
        print("No song directories found.")
        return

    print(f"Found {len(song_dirs)} song(s) to process.\n")

    with MongoHandler() as mongo:
        for song_dir in sorted(song_dirs):
            song_name = song_dir.name
            print(f"── {song_name}")

            # Find all files in this song's directory
            local_files = list(song_dir.iterdir())
            if not local_files:
                print("   (empty — skipping)")
                continue

            lyrics_s3_key     = None
            alignment_s3_key  = None

            for local_file in local_files:
                if local_file.name.startswith("."):
                    continue                     # skip .DS_Store etc.

                s3_key = f"songs/{song_name}/{local_file.name}"

                if object_exists(s3_key):
                    print(f"  ⏭️  already in S3 → {local_file.name}")
                else:
                    upload_file(str(local_file), s3_key)

                # Track paths we need to store in MongoDB
                if local_file.suffix == ".txt":
                    lyrics_s3_key = s3_key
                elif local_file.name == "alignment.json":
                    alignment_s3_key = s3_key

            # Update MongoDB record with S3 key paths
            existing = mongo.get_song_by_title(song_name, exact_match=False)
            if existing:
                update = {}
                if lyrics_s3_key:
                    update["lyrics"] = lyrics_s3_key
                if alignment_s3_key:
                    update["timestamp_lyrics"] = alignment_s3_key
                if update:
                    mongo.update_song(existing["title"], update)
                    print(f"  📝 MongoDB updated: {update}")
                else:
                    print("  ℹ️  No lyrics/alignment found — MongoDB unchanged.")
            else:
                print(f"  ⚠️  Song not found in MongoDB: '{song_name}'")

            print()

    print("✅ Migration complete.")


if __name__ == "__main__":
    main()
