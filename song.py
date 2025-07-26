import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
import os
from dotenv import load_dotenv
from mongo import MongoHandler, get_all_songs, get_song, insert_song
from s3_handler import storage

load_dotenv()

router = APIRouter()

@router.get("/list")
def get_all_songs_endpoint():
    """Get all songs from the database"""
    try:
        songs = get_all_songs()
        return {"songs": songs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching songs: {e}")

class SongRequest(BaseModel):
    song_name: str

@router.post("/prepare")
def prepare_song(req: SongRequest):
    """Prepare a song - check if exists, if not create it using coaching function"""
    song_name = req.song_name.strip().lower()
    
    try:
        # Use the mongo handler to check if song exists
        with MongoHandler() as handler:
            # Search using normalized title (partial match)
            song = handler.get_song_by_normalized_title(handler.normalize_text(song_name))
            
            if song:
                return {
                    "message": "Song already prepared",
                    "song_data": song
                }
            print("to coaching")
            # Song not found, call coaching function to prepare
         
            from coaching import coaching
                 
            try:
                
                song_data = coaching(song_name)
                song_data["normalized_title"] = handler.normalize_text(song_data['title'])
                
                # Insert the new song
                success = handler.insert_song(song_data)
                if not success:
                    raise HTTPException(status_code=500, detail="Failed to save song to database")
                
                # Remove _id if present for response
                if "_id" in song_data:
                    song_data.pop("_id")
                
                print(song_data)
                return {
                    "message": "Song prepared successfully",
                    "song_data": song_data
                }
                
            except Exception as e:
                print(e)
                raise HTTPException(status_code=500, detail=f"Error preparing song: {e}")
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@router.post("/get_song")
def getSong(req: SongRequest):
    """Get song lyrics and audio files from local directory"""
    try:
        file_path = f"songs/{req.song_name}/"
       
        song = get_song(req.song_name)

        # Check if directory exists
        # if not os.path.exists(file_path):
        #     raise HTTPException(status_code=404, detail=f"Song directory not found: {file_path}")
        
        lyrics= ""
        f1 = file_path + "vocals.wav"
        f2=file_path + "accompaniment.wav"
        if storage.is_production:
            lyrics = storage.read_file(song['lyrics'])
            timestamp_lyrics = storage.read_file(song['timestamp_lyrics'])
            file_path = f"s3://idol-singing-coach/songs/{req.song_name}/"
            f1 = storage.get_presigned_url(f1)
            f2 = storage.get_presigned_url(f2)
        else:
            directory = os.listdir(file_path)
            lyrics = ""
            timestamp_lyrics = ""
            # Find and read lyrics file
            for file in directory:
                if file.endswith(".txt"):
                    with open(file_path + file, "r", encoding='utf-8') as f:
                        lyrics = f.read()
                if file =="alignment.json":
                    with open(file_path + file, "r", encoding='utf-8') as f:
                        timestamp_lyrics = f.read()
        
        return {
            "lyrics": lyrics,
            "timestamp_lyrics":timestamp_lyrics,
            "audio_urls": [f1
                ,f2
                
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting song files: {e}")

if __name__ == "__main__":
    # Loading songs_db.json to mongo using the new handler
    try:
        with MongoHandler() as handler:
            # Load songs from JSON file
            success = handler.load_songs_from_json('songs/songs_db.json')
            if success:
                print("Songs loaded successfully to MongoDB!")
            else:
                print("Failed to load songs to MongoDB")
                
    except Exception as e:
        print(f"Error loading songs to MongoDB: {e}")