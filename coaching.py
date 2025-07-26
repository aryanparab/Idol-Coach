from scripts.song_fetcher import fetch_song_by_name
from scripts.extract_from_audio import separate_vocals
from scripts.align_gentle import gentle_aligner
from s3_handler import storage # Import the storage handler
from mongo import MongoHandler  # Import the MongoDB handler
import json 
import os

def coaching(song_name):
    if song_name == "":
        song_name = input("enter song name : ")
    
    # Check if song already exists in MongoDB
    with MongoHandler() as mongo_handler:
        existing_song = mongo_handler.get_song_by_title(song_name)
        if existing_song:
            print(f"Song '{song_name}' already exists in database")
            return existing_song
    
    # Process new song
    song_details = fetch_song_by_name(song_name)
    title = song_details['title']
    downloaded_audio = song_details['audio_path']
    vocals, accomp = separate_vocals(downloaded_audio, song_details['title'], f"songs/{song_details['title']}")
    
    # Read lyrics using storage handler
    lyrics = storage.read_file(song_details['lyrics'])
    
    json_path_aligned, _ = gentle_aligner(vocals, lyrics, f"songs/{song_details['title']}")
    
    new_entry = {
        "title": song_details["title"],
        "downloaded_audio": downloaded_audio,
        "vocals_path": vocals,
        "accompany_path": accomp,
        "lyrics": song_details['lyrics'],
        "timestamp_lyrics": json_path_aligned,
        "artist": song_details.get("artist", ""),
        "youtube_url": song_details.get("youtube_url", "")
    }
    
    # Save to MongoDB instead of JSON file
    with MongoHandler() as mongo_handler:
        success = mongo_handler.insert_song(new_entry)
        if success:
            print(f"✅ Song '{title}' saved to MongoDB")
        else:
            print(f"❌ Failed to save song '{title}' to MongoDB")
    
    # Also maintain JSON backup if needed
    db_path = "songs/songs_db.json"
    try:
        # Read existing database using storage handler
        if storage.file_exists(db_path):
            data = json.loads(storage.read_file(db_path))
        else:
            data = []

        # Check if song already exists in JSON
        if not any(s["title"].lower() == title.lower() for s in data):
            data.append(new_entry)
            # Save updated database using storage handler
            storage.write_file(db_path, json.dumps(data, indent=4))
            print(f"✅ Song '{title}' also saved to JSON backup")
    except Exception as e:
        print(f"⚠️ Warning: Could not update JSON backup: {e}")
            
    return new_entry

if __name__ == "__main__":
    coaching("")