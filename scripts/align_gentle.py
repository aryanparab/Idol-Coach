import requests
import json 
from s3_handler import storage  # Import the storage handler

#docker run -p 8765:8765 lowerquality/gentle
def align_with_gentle(audio_path: str, transcript: str, gentle_url="http://localhost:8765/transcriptions?async=false"):
    # Read audio file using storage handler
    if storage.is_production:
        audio_data = storage.read_file(audio_path, 'rb')
        files = {
            'audio': ('audio.wav', audio_data, 'audio/wav'),
            'transcript': (None, transcript)
        }
    else:
        with open(audio_path, "rb") as audio_file:
            audio_data = audio_file.read()
            files = {
                'audio': ('audio.wav', audio_data, 'audio/wav'),
                'transcript': (None, transcript)
            }
    
    print("Sending request to Gentle")
    response = requests.post(gentle_url, files=files)
    if response.status_code == 200:
        print("Yes")
        return response.json()
    else:
        print(f"{response.status_code} {response.text}")
        return Exception(f"Gentle alignment failed: {response.status_code} {response.text}")
        
def parse_gentle_output(gentle_json):
    aligned_words = []
    for word_info in gentle_json.get('words', []):
        if word_info['case'] == 'success':
            aligned_words.append({
                'word': word_info['word'],
                'start': word_info['start'],
                'end': word_info['end']
            })
    return aligned_words

def save_json(aligned_words, json_path="alignment.json"):
    # Use storage handler to save JSON
    json_content = json.dumps(aligned_words, indent=2)
    storage.write_file(json_path, json_content)
    print(f"Saved alignment JSON to {storage.get_file_url(json_path)}")
    return json_path

def save_srt(aligned_words, srt_path="alignment.srt"):
    def format_srt_time(seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    srt_content = ""
    for i, word in enumerate(aligned_words, start=1):
        start_time = format_srt_time(word['start'])
        end_time = format_srt_time(word['end'])
        srt_content += f"{i}\n{start_time} --> {end_time}\n{word['word']}\n\n"
    
    # Use storage handler to save SRT
    storage.write_file(srt_path, srt_content)
    print(f"Saved alignment SRT to {storage.get_file_url(srt_path)}")
    return srt_path

def gentle_aligner(audio_path, transcript, file_name):
    result_json = align_with_gentle(audio_path, transcript)
    aligned_words = parse_gentle_output(result_json)

    print("Aligned words with timestamps:")
    for w in aligned_words:
        print(f"{w['word']:15s} | start: {w['start']:.3f} | end: {w['end']:.3f}")

    j = save_json(aligned_words, f"{file_name}/alignment.json")
    s = save_srt(aligned_words, f"{file_name}/alignment.srt")
    return j, s

if __name__=="__main__":
    align_with_gentle("songs/My Heart Will Go On -Titanic (lyrics video)/vocals.wav","songs/My Heart Will Go On -Titanic (lyrics video)/My Heart Will Go On -Titanic (lyrics video).txt")
