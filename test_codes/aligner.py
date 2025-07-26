#!/usr/bin/env python3
"""
Safe Vocal-Lyrics Alignment Tool - Cleaned Version
Uses minimal dependencies for maximum compatibility
"""

import json
import re
import subprocess
import wave
from pathlib import Path
from typing import List, Dict, Optional

def safe_import(module_name: str, pip_name: str = None):
    """Safely import optional modules"""
    try:
        return __import__(module_name), True
    except ImportError:
        print(f"Warning: {module_name} not available. Install with: pip install {pip_name or module_name}")
        return None, False

numpy, HAS_NUMPY = safe_import('numpy')

class SafeVocalAligner:
    """Safe vocal alignment tool using basic audio processing"""
    
    def __init__(self, audio_file: str, lyrics: str):
        self.audio_file = Path(audio_file)
        self.lyrics = lyrics
        self.words = []
        self.duration = 0.0
        self.alignment_results = []
        
    def get_audio_duration(self) -> float:
        """Get audio duration using multiple methods"""
        # Try ffprobe first
        try:
            cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', str(self.audio_file)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return float(data['format']['duration'])
        except:
            pass
        
        # Try wave module for WAV files
        if self.audio_file.suffix.lower() == '.wav':
            try:
                with wave.open(str(self.audio_file), 'rb') as wav_file:
                    return wav_file.getnframes() / wav_file.getframerate()
            except:
                pass
        
        # Fallback: estimate from file size
        file_size = self.audio_file.stat().st_size
        return max(10.0, (file_size * 8) / (128 * 1000))  # Rough estimate
    
    def preprocess_lyrics(self) -> List[str]:
        """Clean and tokenize lyrics"""
        lines = [line.strip() for line in self.lyrics.strip().split('\n') if line.strip()]
        full_text = ' '.join(lines)
        cleaned_text = re.sub(r"[^\w\s']", ' ', full_text)
        self.words = [word.strip().lower() for word in cleaned_text.split() if word.strip()]
        return self.words
    
    def time_based_alignment(self, use_weights: bool = True) -> List[Dict]:
        """Align words based on timing (simple or weighted)"""
        if not self.words:
            return []
        
        if use_weights:
            # Calculate word weights based on length and type
            weights = []
            for word in self.words:
                weight = len(word)
                if word in ['a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to']:
                    weight *= 0.7
                elif len(word) >= 7:
                    weight *= 1.3
                elif word.endswith('ing'):
                    weight *= 1.1
                weights.append(weight)
            
            # Normalize weights
            total_weight = sum(weights)
            durations = [(w / total_weight) * self.duration for w in weights]
        else:
            # Simple equal distribution
            durations = [self.duration / len(self.words)] * len(self.words)
        
        # Create alignment results
        results = []
        current_time = 0.0
        method = "weighted_time" if use_weights else "simple_time"
        
        for word, duration in zip(self.words, durations):
            results.append({
                "word": word,
                "start": round(current_time, 3),
                "end": round(current_time + duration, 3),
                "duration": round(duration, 3),
                "method": method
            })
            current_time += duration
        
        return results
    
    def whisper_alignment(self) -> List[Dict]:
        """Use external whisper if available"""
        try:
            subprocess.run(['whisper', '--help'], capture_output=True, timeout=5)
            
            cmd = [
                'whisper', str(self.audio_file), '--model', 'tiny',
                '--output_format', 'json', '--word_timestamps', 'True', '--output_dir', '.'
            ]
            
            result = subprocess.run(cmd, capture_output=True, timeout=60)
            
            if result.returncode == 0:
                json_file = self.audio_file.with_suffix('.json')
                if json_file.exists():
                    with open(json_file) as f:
                        data = json.load(f)
                    
                    # Extract word timestamps and match to lyrics
                    whisper_words = []
                    for segment in data.get('segments', []):
                        if 'words' in segment:
                            whisper_words.extend(segment['words'])
                    
                    json_file.unlink()  # Clean up
                    return self._match_whisper_to_lyrics(whisper_words)
        except:
            pass
        
        return []
    
    def _match_whisper_to_lyrics(self, whisper_words: List[Dict]) -> List[Dict]:
        """Match whisper transcription to lyrics"""
        results = []
        whisper_idx = 0
        
        for lyric_word in self.words:
            if whisper_idx < len(whisper_words):
                whisper_word = whisper_words[whisper_idx]
                word_similar = self._words_similar(lyric_word, whisper_word['word'].strip().lower())
                
                results.append({
                    "word": lyric_word,
                    "start": whisper_word['start'],
                    "end": whisper_word['end'],
                    "method": "whisper_matched" if word_similar else "whisper_mismatch",
                    "whisper_word": whisper_word['word']
                })
                whisper_idx += 1
            else:
                # Estimate timing for remaining words
                last_end = results[-1]['end'] if results else 0
                results.append({
                    "word": lyric_word,
                    "start": last_end,
                    "end": last_end + 0.5,
                    "method": "estimated"
                })
        
        return results
    
    def _words_similar(self, word1: str, word2: str) -> bool:
        """Check if words are similar"""
        word1, word2 = word1.lower().strip(), word2.lower().strip()
        if word1 == word2 or word1 in word2 or word2 in word1:
            return True
        
        # Character overlap check
        set1, set2 = set(word1), set(word2)
        overlap = len(set1 & set2)
        union = len(set1 | set2)
        return (overlap / union if union > 0 else 0) > 0.6
    
    def align(self, method: str = "auto") -> List[Dict]:
        """Main alignment function"""
        if not self.audio_file.exists():
            print(f"Error: Audio file '{self.audio_file}' not found")
            return []
        
        self.duration = self.get_audio_duration()
        self.preprocess_lyrics()
        
        if not self.words:
            print("No words found in lyrics")
            return []
        
        # Choose alignment method
        if method == "auto":
            results = self.whisper_alignment()
            if not results:
                results = self.time_based_alignment(use_weights=True)
        elif method == "whisper":
            results = self.whisper_alignment()
        elif method == "weighted":
            results = self.time_based_alignment(use_weights=True)
        else:  # simple
            results = self.time_based_alignment(use_weights=False)
        
        self.alignment_results = results
        print(f"Alignment completed: {len(results)} words aligned")
        return results
    
    def export_results(self, json_file: str = "alignment.json", srt_file: str = "alignment.srt"):
        """Export results to JSON and SRT formats"""
        if not self.alignment_results:
            print("No results to export")
            return
        
        # Export JSON
        data = {
            "audio_file": str(self.audio_file),
            "lyrics": self.lyrics,
            "duration": self.duration,
            "word_count": len(self.words),
            "alignment": self.alignment_results
        }
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Export SRT
        def format_srt_time(seconds):
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = int(seconds % 60)
            ms = int((seconds % 1) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
        
        with open(srt_file, 'w', encoding='utf-8') as f:
            for i, result in enumerate(self.alignment_results, 1):
                start_time = format_srt_time(result['start'])
                end_time = format_srt_time(result['end'])
                f.write(f"{i}\n{start_time} --> {end_time}\n{result['word']}\n\n")
        
        print(f"Results exported to {json_file} and {srt_file}")
    
    def print_summary(self):
        """Print alignment summary"""
        if not self.alignment_results:
            print("No alignment results")
            return
        
        print(f"\nAlignment Summary:")
        print(f"Audio: {self.audio_file}")
        print(f"Duration: {self.duration:.2f}s | Words: {len(self.alignment_results)}")
        print("-" * 50)
        
        for i, result in enumerate(self.alignment_results, 1):
            duration = result['end'] - result['start']
            print(f"{i:2d}. {result['word']:15s} | {result['start']:6.2f}s-{result['end']:6.2f}s | {result['method']}")

def main():
    """Example usage"""
    audio_file = "vocals.wav"  # Change this
    lyrics = """
    Your lyrics here
    Multiple lines supported
    """
    
    aligner = SafeVocalAligner(audio_file, lyrics)
    
    # Run alignment
    results = aligner.align(method="auto")
    
    if results:
        aligner.print_summary()
        aligner.export_results("my_alignment.json", "my_alignment.srt")
    else:
        print("Alignment failed")

if __name__ == "__main__":
    main()