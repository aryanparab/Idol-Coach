from demucs import pretrained
from demucs.apply import apply_model
from demucs.audio import AudioFile
import os
import re
import soundfile as sf
import tempfile
from s3_handler import storage  # Import the storage handler

def separate_vocals(audio_path, song_name, out_dir):
    model = pretrained.get_model('htdemucs')
    model.cpu()
    model.eval()

    # Handle S3 vs local file reading
    print(f"reading file: {audio_path}")
    
    if storage.is_production:
        # In production, always treat as S3 file
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
            temp_path = temp_file.name
            
        try:
            # Use the audio_path as the S3 key directly
            print(f"Downloading from S3: {audio_path}")
            audio_data = storage.read_file(audio_path, mode='rb')
            with open(temp_path, 'wb') as f:
                f.write(audio_data)
            
            # Now read with AudioFile
            wav = AudioFile(temp_path).read(samplerate=44100)
            
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    else:
        # Local file - read directly
        wav = AudioFile(audio_path).read(samplerate=44100)
    
    sr = 44100
    
    # Add batch dimension if missing
    if wav.dim() == 2:  # shape (channels, samples)
        wav = wav.unsqueeze(0)  # shape (1, channels, samples)

    # Apply separation
    print("Applying model for separation ....")
    sources = apply_model(model, wav, device='cpu', split=True, overlap=0.25)[0]

    sources_list = model.sources  # ['drums', 'bass', 'other', 'vocals']

    print("Saving all sources...")
    
    # Save vocals using storage handler
    vocals_path = os.path.join(out_dir, "vocals.wav")
    for i, source in enumerate(sources_list):
        if source == "vocals":
            storage.write_audio_file(vocals_path, sources[i].cpu().numpy().T, sr)
            break

    # Combine other sources for accompaniment
    other_sources = [sources[i] for i, s in enumerate(sources_list) if s != "vocals"]
    accompaniment = sum(other_sources)
    accompaniment_path = os.path.join(out_dir, "accompaniment.wav")
    
    # Save accompaniment using storage handler
    storage.write_audio_file(accompaniment_path, accompaniment.cpu().numpy().T, sr)

    return vocals_path, accompaniment_path

if __name__ == "__main__":
    vocals, accompaniment = separate_vocals("songs/Lady Gaga, Bruno Mars - Die With A Smile (Lyrics)/zgaCZOQCpp8.mp3","Lady Gaga, Bruno Mars - Die With A Smile (Lyrics)","songs/Lady Gaga, Bruno Mars - Die With A Smile (Lyrics)")
    print("Vocals saved at:", vocals)
    print("Accompaniment saved at:", accompaniment)