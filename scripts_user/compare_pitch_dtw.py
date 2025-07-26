import numpy as np
import librosa
from dtw import dtw
from scipy.spatial.distance import euclidean
from s3_handler import storage  # Import the global storage handler
import tempfile
import os

def extract_pitch_contour(audio_path, sr=16000):
    """Extract pitch contour from audio file, handling both local and S3 storage"""
    if storage.is_production and storage.file_exists(audio_path):
        # For S3, download to temporary file first
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            audio_data = storage.read_file(audio_path, mode='rb')
            temp_file.write(audio_data)
            temp_file.flush()
            
            # Load audio from temporary file
            y, sr = librosa.load(temp_file.name, sr=sr)
            
            # Clean up temporary file
            os.unlink(temp_file.name)
    else:
        # For local storage or when not in production
        y, sr = librosa.load(audio_path, sr=sr)
    
    pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
    pitch_contour = []

    for i in range(pitches.shape[1]):
        index = magnitudes[:,i].argmax()
        pitch = pitches[index,i]
        pitch_contour.append(pitch if pitch > 0 else 0)

    return np.array(pitch_contour)

def compare_with_dtw(user_pitch, ref_pitch):
    user_pitch = user_pitch.reshape(-1,1)
    ref_pitch = ref_pitch.reshape(-1,1)

    alignment = dtw(
        user_pitch, ref_pitch, keep_internals=True
    )

    return {
        "distance": alignment.normalizedDistance,
        "path": alignment.index1s,
        "cost_matrix": alignment.costMatrix
    }

def segment_pitch_contour(full_contour, sr, start_time, end_time, hop_length=512):
    start_frame = int((start_time * sr) / hop_length)
    end_frame = int((end_time * sr) / hop_length)
    return full_contour[start_frame:end_frame]

def save_pitch_analysis(pitch_data, file_path):
    """Save pitch analysis results to storage"""
    import json
    
    # Convert numpy arrays to lists for JSON serialization
    serializable_data = {}
    for key, value in pitch_data.items():
        if isinstance(value, np.ndarray):
            serializable_data[key] = value.tolist()
        else:
            serializable_data[key] = value
    
    storage.write_file(file_path, json.dumps(serializable_data, indent=2))

def load_pitch_analysis(file_path):
    """Load pitch analysis results from storage"""
    import json
    
    if storage.file_exists(file_path):
        content = storage.read_file(file_path)
        data = json.loads(content) if isinstance(content, str) else content
        
        # Convert lists back to numpy arrays where appropriate
        for key, value in data.items():
            if isinstance(value, list) and key in ['pitch_contour', 'cost_matrix']:
                data[key] = np.array(value)
        
        return data
    else:
        return None