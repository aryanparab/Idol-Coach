import json
import difflib
from typing import List, Dict, Tuple, Optional
import difflib
from fuzzywuzzy import fuzz, process
import re
import numpy as np
from collections import defaultdict

def load_gentle_alignment(gentle_json_path: str) -> List[Dict]:
    """Load Gentle-aligned full song transcription."""
    with open(gentle_json_path, 'r') as f:
        data = json.load(f)
    return data


def load_user_transcription(user_json_path: str) -> List[Dict]:
    """Load user transcription aligned with Whisper."""
    with open(user_json_path, 'r') as f:
        data = json.load(f)
    return data["alignment"]


def get_words_only(alignment: List[Dict]) -> List[str]:
    """Extract word list from alignment for comparison."""

    return [w["word"].strip().lower() for w in alignment if w["word"].strip()]

def preprocess_lyrics(text: str) -> str:
    """Aggressive preprocessing for singing transcriptions"""
    # Convert to lowercase
    text = text.lower()
    # Remove common filler words that appear in singing but not lyrics
    fillers = ['uh', 'um', 'ah', 'oh', 'yeah', 'hey', 'wow', 'mmm']
    words = text.split()
    words = [w for w in words if w not in fillers]
    text = ' '.join(words)
    # Remove punctuation but keep apostrophes for contractions
    text = re.sub(r"[^\w\s']", '', text)
    # Handle common singing variations
    replacements = {
        "gonna": "going to",
        "wanna": "want to", 
        "gotta": "got to",
        "gimme": "give me",
        "lemme": "let me",
        "'em": "them",
        "y'all": "you all",
        "ain't": "is not"
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    return ' '.join(text.split())

def calculate_sequence_similarity(user_words: List[str], song_segment: List[str]) -> float:
    """
    Calculate similarity focusing on word sequence matching.
    This gives higher scores to segments that contain the user's words in order.
    """
    user_text = preprocess_lyrics(' '.join(user_words))
    segment_text = preprocess_lyrics(' '.join(song_segment))
    
    user_word_list = user_text.split()
    segment_word_list = segment_text.split()
    
    # Strategy 1: Check for subsequence matching (words in order)
    subsequence_score = 0
    user_idx = 0
    matches_in_order = 0
    
    for segment_word in segment_word_list:
        if user_idx < len(user_word_list):
            if fuzz.ratio(user_word_list[user_idx], segment_word) > 80:
                matches_in_order += 1
                user_idx += 1
    
    if len(user_word_list) > 0:
        subsequence_score = matches_in_order / len(user_word_list)
    
    # Strategy 2: Standard fuzzy matching
    fuzzy_scores = [
        fuzz.ratio(user_text, segment_text),
        fuzz.partial_ratio(user_text, segment_text),
        fuzz.token_sort_ratio(user_text, segment_text),
        fuzz.token_set_ratio(user_text, segment_text)
    ]
    
    fuzzy_average = sum(fuzzy_scores) / len(fuzzy_scores) / 100.0
    
    # Strategy 3: Word coverage (how many user words appear in segment)
    user_words_found = 0
    for user_word in user_word_list:
        for segment_word in segment_word_list:
            if fuzz.ratio(user_word, segment_word) > 70:
                user_words_found += 1
                break
    
    coverage_score = user_words_found / len(user_word_list) if user_word_list else 0
    
    # Combine scores with emphasis on sequence matching
    final_score = (
        subsequence_score * 0.5 +  # Sequence matching is most important
        fuzzy_average * 0.3 +      # General similarity
        coverage_score * 0.2       # Word coverage
    )
    
    return final_score

def find_best_segment_match(song_words: List[str], 
                           user_words: List[str],
                           full_song_alignment: List[Dict],
                           min_segment_length: int = None,
                           max_segment_length: int = None) -> List[Dict]:
    """
    Find the best matching segment in the song for the user's input.
    This tries different segment lengths and finds the one with highest confidence.
    """
    if not user_words or not song_words:
        return []
    
    user_word_count = len(user_words)
    
    # Set reasonable segment length bounds - be more generous to capture full phrases
    if min_segment_length is None:
        min_segment_length = max(user_word_count, 3)  # At least as long as user input
    if max_segment_length is None:
        max_segment_length = min(len(song_words), user_word_count * 4)  # Up to 4x user length
    
    results = []
    
    # Try different segment lengths, starting with lengths close to user input
    segment_lengths = []
    
    # Prioritize lengths around the user input length
    for multiplier in [1.0, 1.2, 0.8, 1.5, 1.8, 0.6, 2.0, 2.5]:
        length = int(user_word_count * multiplier)
        if min_segment_length <= length <= max_segment_length and length not in segment_lengths:
            segment_lengths.append(length)
    
    for segment_length in segment_lengths:
        if segment_length > len(song_words):
            continue
            
        # Slide the window across the song
        for start_idx in range(len(song_words) - segment_length + 1):
            end_idx = start_idx + segment_length
            segment = song_words[start_idx:end_idx]
            
            # Use improved sequence similarity calculation
            confidence = calculate_sequence_similarity(user_words, segment)
            
            # Only keep good matches - higher threshold for better precision
            if confidence >= 0.3:  # Reasonable threshold
                if end_idx <= len(full_song_alignment):
                    user_text = preprocess_lyrics(' '.join(user_words))
                    segment_text = preprocess_lyrics(' '.join(segment))
                    
                    results.append({
                        "confidence": confidence,
                        "start_time": full_song_alignment[start_idx]["start"],
                        "end_time": full_song_alignment[end_idx - 1]["end"],
                        "song_words_snippet": segment,
                        "matched_segment_timings": full_song_alignment[start_idx:end_idx],
                        "segment_length": segment_length,
                        "user_text": user_text,
                        "segment_text": segment_text,
                        "word_start_idx": start_idx,
                        "word_end_idx": end_idx
                    })
    
    # Sort by confidence and return top results
    results.sort(key=lambda x: x["confidence"], reverse=True)
    return results

def expand_match_intelligently(best_match: Dict, 
                             song_words: List[str],
                             full_song_alignment: List[Dict],
                             user_words: List[str]) -> Dict:
    """
    Take the best match and intelligently expand it to include more context
    by checking adjacent segments for continued similarity.
    """
    start_idx = best_match["word_start_idx"]
    end_idx = best_match["word_end_idx"]
    
    # Don't expand if the match already covers most user words well
    if best_match["confidence"] > 0.8:
        return best_match
    
    # Try expanding backwards (look for earlier parts of the phrase)
    extended_start = start_idx
    for i in range(start_idx - 1, max(0, start_idx - 8), -1):
        extended_segment = song_words[i:end_idx]
        extended_confidence = calculate_sequence_similarity(user_words, extended_segment)
        
        if extended_confidence > best_match["confidence"] * 1.05:  # At least 5% better
            extended_start = i
            best_match["confidence"] = extended_confidence
        else:
            break
    
    # Try expanding forwards (look for later parts of the phrase)  
    extended_end = end_idx
    for i in range(end_idx + 1, min(len(song_words), end_idx + 8)):
        extended_segment = song_words[extended_start:i]
        extended_confidence = calculate_sequence_similarity(user_words, extended_segment)
        
        if extended_confidence > best_match["confidence"] * 1.05:  # At least 5% better
            extended_end = i
            best_match["confidence"] = extended_confidence
        else:
            break
    
    # Create expanded result if we found improvements
    if extended_start != start_idx or extended_end != end_idx:
        extended_segment = song_words[extended_start:extended_end]
        
        return {
            "confidence": best_match["confidence"],
            "start_time": full_song_alignment[extended_start]["start"],
            "end_time": full_song_alignment[extended_end - 1]["end"],
            "song_words_snippet": extended_segment,
            "matched_segment_timings": full_song_alignment[extended_start:extended_end],
            "word_start_idx": extended_start,
            "word_end_idx": extended_end,
            "was_expanded": True,
            "original_range": (start_idx, end_idx)
        }
    
    return best_match

def identify_sung_part_improved(song_words: List[str],
                               user_words: List[str], 
                               full_song_alignment: List[Dict],
                               return_best_only: bool = True,
                               expand_match: bool = True):
    """
    Improved function to identify which part of the song the user is singing.
    This version finds the best matching segment regardless of user input length.
    
    Args:
        song_words: Complete song lyrics as list of words
        user_words: User's sung words (from Whisper transcription)
        full_song_alignment: Timing alignment for each word
        return_best_only: If True, return only the best match; if False, return top 3
        expand_match: If True, try to intelligently expand the best match
    
    Returns:
        Dictionary with match information or list of matches
    """
    matches = find_best_segment_match(song_words, user_words, full_song_alignment)
    
    if not matches:
        return None if return_best_only else []
    
    # Get the best match
    best_match = matches[0]
    
    # Optionally expand the match to include more context
    if expand_match:
        best_match = expand_match_intelligently(best_match, song_words, full_song_alignment, user_words)
    
    if return_best_only:
        return {
            "found_match": True,
            "confidence": best_match["confidence"],
            "start_time": best_match["start_time"],
            "end_time": best_match["end_time"],
            "duration_seconds": best_match["end_time"] - best_match["start_time"],
            "song_words_snippet": ' '.join(best_match["song_words_snippet"]),
            "user_input": ' '.join(user_words),
            "timing_data": best_match["matched_segment_timings"],
            "match_details": {
                "segment_length": len(best_match["song_words_snippet"]),
                "was_expanded": best_match.get("was_expanded", False),
                "word_indices": (best_match["word_start_idx"], best_match["word_end_idx"])
            }
        }
    else:
        return [
            {
                "confidence": match["confidence"],
                "start_time": match["start_time"],
                "end_time": match["end_time"],
                "song_words_snippet": ' '.join(match["song_words_snippet"]),
                "duration_seconds": match["end_time"] - match["start_time"],
                "segment_length": len(match["song_words_snippet"])
            }
            for match in matches[:3]
        ]

# Keep your original functions for backward compatibility
def sliding_window_match(song_words: List[str],
                         user_words: List[str],
                         full_song_alignment: List[Dict],
                         threshold: float = 0.6):
    """Original sliding window function - kept for backward compatibility"""
    window_size = len(user_words)
    results = []

    for i in range(len(song_words) - window_size + 1):
        segment = song_words[i:i + window_size]
        matcher = difflib.SequenceMatcher(None, segment, user_words)
        match_ratio = matcher.ratio()

        if match_ratio >= threshold:
            matched_segment_timings = full_song_alignment[i:i + window_size]
            start_time = matched_segment_timings[0]["start"]
            end_time = matched_segment_timings[-1]["end"]

            results.append({
                "match_ratio": match_ratio,
                "start_time": start_time,
                "end_time": end_time,
                "song_words_snippet": segment,
                "matched_segment_timings": matched_segment_timings
            })

    results.sort(key=lambda x: x["match_ratio"], reverse=True)
    return results

def identify_sung_part(song_words: List[str],
                      user_words: List[str], 
                      full_song_alignment: List[Dict],
                      return_best_only: bool = True):
    """Original function - now calls the improved version"""
    return identify_sung_part_improved(song_words, user_words, full_song_alignment, return_best_only)


# Example usage with debug output
if __name__ == "__main__":
    # Test with your actual data
    user_data = ""
    song_data=""
    with open('user_transcription.json','r') as file:
        user_data = json.load(file)
    with open("songs/Ed Sheeran, Pokémon - Celestial (Lyrics)/alignment.json",'r') as file:
        song_data = json.load(file)
    
    song_words = get_words_only(song_data)
 
    user_words = get_words_only(user_data["alignment"])
    
    print("Song words:", song_words[:10])  # First 10 words
    print("User words:", user_words)
    
    # Use the improved function
    result = identify_sung_part_improved(song_words, user_words, song_data)
    
    if result:
        print("\nBest Match Found:")
        print(f"Confidence: {result['confidence']:.3f}")
        print(f"Song Segment: {result['song_words_snippet']}")
        print(f"Time Range: {result['start_time']:.2f}s - {result['end_time']:.2f}s")
        print(f"Duration: {result['duration_seconds']:.2f}s")
        print(f"User Input: {result['user_input']}")
        if result['match_details']['was_expanded']:
            print("Note: Match was intelligently expanded for better coverage")
    else:
        print("No good match found")
        
    # Show top 3 matches for debugging
    print("\n--- Top 3 Matches for Debugging ---")
    top_matches = identify_sung_part_improved(song_words, user_words, song_data, return_best_only=False)
    for i, match in enumerate(top_matches[:3], 1):
        print(f"\nMatch #{i}:")
        print(f"  Confidence: {match['confidence']:.3f}")
        print(f"  Segment: {match['song_words_snippet']}")
        print(f"  Time: {match['start_time']:.2f}s - {match['end_time']:.2f}s")