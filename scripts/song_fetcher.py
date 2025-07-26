# song_fetcher.py

import os
import subprocess
import json
import yt_dlp
from dotenv import load_dotenv
from scripts.agents import extract_title_artist
import boto3
import soundfile as sf
import io
from urllib.parse import quote
from scripts.get_lyrics_from_genius import fetch_lyrics
from s3_handler import storage  # Import the storage handler
load_dotenv() 

def search_youtube(query: str):
    """Search YouTube for the top result using yt-dlp."""
    query = query + " lyric video"
    command = [
        "yt-dlp",
        f"ytsearch1:{query}",
        "--print-json",
        "--skip-download"
    ]
    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode != 0 or not result.stdout.strip():
        return None

    video_info = json.loads(result.stdout.strip())
    return {
        "title": video_info["title"],
        "channel": video_info["channel"],
        "url": video_info["webpage_url"],
        "id": video_info["id"],
        "duration": video_info.get("duration")
    }

def download_audio(video_url: str, output_dir):
    """Download audio from YouTube and return the file path."""
    # Ensure directory exists
    storage.ensure_directory_exists(output_dir)
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{output_dir}/%(id)s.%(ext)s',
        'quiet': True,
        'noplaylist': True,
        'no_warnings': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=True)
        base = ydl.prepare_filename(info)
        # Normalize to .mp3
        audio_path = os.path.splitext(base)[0] + ".mp3"
    
    # If production mode, upload the downloaded file to S3
    if storage.is_production and os.path.exists(audio_path):
        with open(audio_path, 'rb') as f:
            audio_content = f.read()
        storage.write_file(audio_path, audio_content, 'wb')
        # Remove local file after upload
        os.remove(audio_path)
    
    return audio_path, info

def fetch_song_by_name(song_query: str):
    """Search for a song and download its audio."""
    print(f"🔍 Searching for: {song_query}")
    video_info = search_youtube(song_query)
    if not video_info:
        return {"error": "No results found on YouTube."}
  
    title = video_info['title']
    channel = video_info['channel']
    url = video_info['url']
    DOWNLOAD_DIR = f"songs/{title}"
    
    # Ensure directory exists
    storage.ensure_directory_exists(DOWNLOAD_DIR)

    print(f"🎬 Found: {title} by {channel}")
    print(f"⬇️ Downloading audio...")
    audio_path, _ = download_audio(url, DOWNLOAD_DIR)
   
    print(f"✅ Downloaded to: {storage.get_file_url(audio_path)}")

    title, channel = extract_title_artist(title)
    lyrics = fetch_lyrics(title, channel)
    lyrics_file = f'{DOWNLOAD_DIR}/{video_info["title"]}.txt'
    
    # Save lyrics using storage handler
    storage.write_file(lyrics_file, lyrics)

    return {
        "title": video_info["title"],
        "artist": video_info["channel"],
        "youtube_url": video_info["url"],
        "audio_path": audio_path,
        "lyrics": lyrics_file
    }

# Run standalone for testing
# if __name__ == "__main__":
#     result = fetch_song_by_name("Coldwater")
#     print(result['lyrics'])