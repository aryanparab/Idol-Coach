from fastapi import APIRouter, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import shutil
import json
import uuid
from typing import Optional
from mongo import MongoHandler, get_song
import os
from process_user_audio import process_user_audio
from scripts.agents import chatbot_agent
from s3_handler import storage

router = APIRouter()

def cleanup_temp_files(user_audio_path, user_transcription_path):
    """Clean up temporary files from storage"""
    try:
        if user_audio_path and storage.file_exists(user_audio_path):
            if storage.is_production:
                # Delete from S3
                storage.s3_client.delete_object(
                    Bucket=storage.bucket_name,
                    Key=user_audio_path
                )
                print(f"✅ Deleted from S3: {user_audio_path}")
            else:
                # Delete local file
                os.remove(user_audio_path)
                print(f"✅ Deleted locally: {user_audio_path}")
                
        if user_transcription_path and storage.file_exists(user_transcription_path):
            if storage.is_production:
                # Delete from S3
                storage.s3_client.delete_object(
                    Bucket=storage.bucket_name,
                    Key=user_transcription_path
                )
                print(f"✅ Deleted transcription from S3: {user_transcription_path}")
            else:
                # Delete local file
                os.remove(user_transcription_path)
                print(f"✅ Deleted transcription locally: {user_transcription_path}")
                
    except Exception as e:
        print(f"⚠️ Warning: Failed to clean up some files: {e}")

@router.post("/analyze")
async def analyze_user_audio(
    audio_file: UploadFile,
    song_name: str = Form(...)
):
    """Analyze user audio against a reference song"""
    print(f"Received: {song_name}, {audio_file.filename}")
    
    # Initialize paths for cleanup
    user_audio_path = None
    user_transcription_path = None
    
    try:
        # Save uploaded file using storage handler
        file_id = str(uuid.uuid4())
        user_audio_path = f"user_vocals/{file_id}_{audio_file.filename}"
        
        # Read the uploaded file content
        audio_content = await audio_file.read()
        
        # Write to storage (S3 in prod, local in dev)
        storage.write_file(user_audio_path, audio_content, mode='wb')

        # Get song metadata from MongoDB using the handler
        with MongoHandler() as handler:
            # Search by exact title match first, then try partial match
            song = handler.get_song_by_title(song_name, exact_match=True)
            if not song:
                # Try partial match if exact match fails
                song = handler.get_song_by_title(song_name, exact_match=False)
        
        print(f"Found song: {song}")
        
        if not song:
            raise HTTPException(status_code=404, detail=f"Song '{song_name}' not found in database")

        # Verify required fields exist
        if "timestamp_lyrics" not in song or "vocals_path" not in song:
            raise HTTPException(
                status_code=400, 
                detail="Song data incomplete - missing timestamp_lyrics or vocals_path"
            )

        # Process the audio analysis
        try:
            analysis = process_user_audio(
                user_audio_path,
                song["timestamp_lyrics"],
                song["vocals_path"],
                file_id  # Pass file_id for transcription naming
            )
            return analysis
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error processing audio: {e}")
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Handle any other unexpected errors
        raise HTTPException(status_code=500, detail=f"Unexpected error during analysis: {e}")
    
    finally:
        # Clean up temporary files
        cleanup_temp_files(user_audio_path, user_transcription_path)


class AnalyzeTextRequest(BaseModel):
    user_text: str
    chat_id: Optional[str] = None

@router.post("/analyze_text")
async def analyze_user_text(request: AnalyzeTextRequest):
    """Analyze user text input using chatbot agent"""
    try:
        if not request.user_text.strip():
            raise HTTPException(status_code=400, detail="User text cannot be empty")
            
        result = chatbot_agent(request.user_text, request.chat_id)
        return {"message": result}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing text: {e}")