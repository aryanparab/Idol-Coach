from transcribe_with_whisper import transcribe_with_whisper
from compare_pitch_dtw import extract_pitch_contour, compare_with_dtw
from s3_handler import storage  # Import the global storage handler
import json
import time

def match_user_recording(user_audio, reference_audio):
    print("Transcribing user recording with Whisper...")
    whisper_output = transcribe_with_whisper(user_audio)

    print("Extracting pitch contours...")
    user_pitch = extract_pitch_contour(user_audio)
    ref_pitch = extract_pitch_contour(reference_audio)

    print("Running DTW pitch comparison...")
    dtw_result = compare_with_dtw(user_pitch, ref_pitch)
    
    # Prepare results
    results = {
        "whisper_text": whisper_output["text"],
        "segments": whisper_output["segments"],
        "pitch_distance": dtw_result["distance"],
        "dtw_path": dtw_result["path"].tolist() if hasattr(dtw_result["path"], 'tolist') else dtw_result["path"],
        "timestamp": time.time(),
        "user_audio_path": user_audio,
        "reference_audio_path": reference_audio
    }
    
    # Save matching results to storage
    results_file_path = f"matching_results_{int(time.time())}.json"
    storage.write_file(results_file_path, json.dumps(results, indent=2))
    
    print(f"✅ Matching results saved to: {storage.get_file_url(results_file_path)}")
    
    return results

def load_matching_results(results_file_path):
    """Load previously saved matching results from storage"""
    if storage.file_exists(results_file_path):
        content = storage.read_file(results_file_path)
        results = json.loads(content) if isinstance(content, str) else content
        
        print(f"✅ Loaded matching results from: {storage.get_file_url(results_file_path)}")
        return results
    else:
        print(f"❌ No matching results found at: {storage.get_file_url(results_file_path)}")
        return None

def save_user_audio_to_storage(audio_data, filename, sample_rate=44100):
    """Save user audio data to storage using the storage handler's audio method"""
    file_path = f"user_recordings/{filename}"
    storage.write_audio_file(file_path, audio_data, sample_rate)
    return file_path

def batch_match_recordings(user_audio_list, reference_audio_list):
    """Process multiple user recordings against reference audio files"""
    batch_results = []
    
    for i, (user_audio, ref_audio) in enumerate(zip(user_audio_list, reference_audio_list)):
        print(f"\n🎵 Processing batch {i+1}/{len(user_audio_list)}")
        
        try:
            result = match_user_recording(user_audio, ref_audio)
            result["batch_index"] = i
            batch_results.append(result)
        except Exception as e:
            print(f"❌ Error processing batch {i+1}: {e}")
            batch_results.append({
                "batch_index": i,
                "error": str(e),
                "user_audio": user_audio,
                "reference_audio": ref_audio
            })
    
    # Save batch results
    batch_file_path = f"batch_matching_results_{int(time.time())}.json"
    storage.write_file(batch_file_path, json.dumps(batch_results, indent=2))
    
    print(f"✅ Batch results saved to: {storage.get_file_url(batch_file_path)}")
    
    return batch_results