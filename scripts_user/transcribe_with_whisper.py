from faster_whisper import WhisperModel
import json
import os 
from s3_handler import storage

def transcribe_with_whisper(filename, output_path):
    """Transcribe audio file and save to specified path using storage handler"""
    model = WhisperModel("tiny", device="cpu")

    # For S3, we need to download the file temporarily for whisper processing
    if storage.is_production:
        # Create a temporary local file for whisper processing
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
            temp_path = temp_file.name
            # Download from S3 to temp file
            audio_content = storage.read_file(filename, mode='rb')
            temp_file.write(audio_content)
        
        # Process with whisper
        segments, info = model.transcribe(temp_path, word_timestamps=True)
        
        # Clean up temp file
        os.unlink(temp_path)
    else:
        # Direct processing for local files
        segments, info = model.transcribe(filename, word_timestamps=True)

    output = []
    for segment in segments:
        for word in segment.words:
            output.append({
                "word": word.word,
                "start": word.start,
                "end": word.end
            })

    # Save transcription using storage handler
    transcription_data = json.dumps({"alignment": output}, indent=2)
    storage.write_file(output_path, transcription_data)
    
    return output_path
