from scripts_user.lyric_matcher import (
    load_gentle_alignment,
    load_user_transcription,
    get_words_only,
    sliding_window_match,
    identify_sung_part
)
import json
import os
import time
import numpy as np
from scripts_user.transcribe_with_whisper import transcribe_with_whisper
from scripts_user.compare_pitch_dtw import extract_pitch_contour
from scripts_user.audio_analysis import analyze_audio_match_enhanced
import librosa
from scripts.agents import coach_agent
from s3_handler import storage  # Import the global storage handler
import numpy as np


def convert_to_serializable(obj):
    """Convert numpy types to Python native types for JSON serialization"""
    if isinstance(obj, dict):
        return {key: convert_to_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_serializable(item) for item in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    else:
        return obj

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


def process_user_audio(user_audio_path, gentle_json_path, reference_audio_path, file_id):
    """Process user audio with proper storage handling"""
    user_transcription_path = None
    
    try:

        # Load gentle alignment from storage
        gentle_json_content = storage.read_file(gentle_json_path)

        gentle_alignment = json.loads(gentle_json_content) if isinstance(gentle_json_content, str) else gentle_json_content
 
        song_words = get_words_only(gentle_alignment)

        print("Transcribing user audio .....")
        
        # Create transcription path using file_id
        user_transcription_path = f"user_transcriptions/{file_id}_transcription.json"
        
        # Transcribe and save to storage
        whisper_path = transcribe_with_whisper(user_audio_path, user_transcription_path)
    
        # Load user transcription from storage
        user_transcription_content = storage.read_file(user_transcription_path)
        
        user_alignment = json.loads(user_transcription_content) if isinstance(user_transcription_content, str) else user_transcription_content
        
        user_words = get_words_only(user_alignment['alignment'])
        print("user words :",user_words)
        print("Determining matching window based on lyrics")
   
    # start_time = time.perf_counter()
    # matches = sliding_window_match(song_words, user_words, gentle_alignment, threshold=0.6)
    # end_time = time.perf_counter()

        user_pitch = extract_pitch_contour(user_audio_path)
        ref_pitch = extract_pitch_contour(reference_audio_path)
        print("Horrayyy")
        sr = 16000
        hop_length = 512
        
        start_time = time.perf_counter()
        match = identify_sung_part(song_words, user_words, gentle_alignment, True)
        end_time = time.perf_counter()
        if not match:
            return "Trouble getting audio"
        
        print(f"\n🎯 Analyzing matched segment: {match['start_time']} - {match['end_time']}")
        
        analysis = analyze_audio_match_enhanced(
                user_audio_path = user_audio_path,
                reference_audio_path= reference_audio_path,
                match = match,
                ref_pitch = ref_pitch,
                sr=sr,
                hop_length=hop_length
            )

            # print("\n🎵 Lyrics:", " ".join(match["song_words_snippet"]))
            # print("🕒 Timing:", match["start_time"], "to", match["end_time"])
            # print("📊 Comparison Metrics:")
            # for key, val in analysis["comparison_metrics"].items():
            #     print(f"  {key}: {val:.4f}" if isinstance(val, float) else f"  {key}: {val}")
            
            # print("\n🗣️ AI Feedback Prompt:")
        
        a = "s"
        a = coach_agent(analysis)
        analysis_serializable = convert_to_serializable(analysis)
        analysis_string = json.dumps(analysis_serializable, indent=2)
        
        # Save analysis results to storage
        results_file_path = f"analysis_results_{int(time.time())}.json"
        storage.write_file(results_file_path, analysis_string)
        
        #print("Analysis,    ", analysis)
        return {"output":a,"voice_analysis":analysis_string}
    finally:
        if user_transcription_path:
            cleanup_temp_files(None, user_transcription_path)


if __name__=="__main__":
    user_vocals = "user_vocals/t1.wav"
    gentle_lyrics ="songs/Somebody That I Used To Know | Gotye | Lyrics Video/alignment.json"
    ref_audio = "songs/Somebody That I Used To Know | Gotye | Lyrics Video/vocals.wav"
    process_user_audio(user_vocals,gentle_lyrics,ref_audio)