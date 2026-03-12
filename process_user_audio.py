import json
import os
import time
import numpy as np

from scripts_user.lyric_matcher import get_words_only, identify_sung_part
from scripts_user.transcribe_with_whisper import transcribe_with_whisper
from scripts_user.compare_pitch_dtw import extract_pitch_contour
from scripts_user.audio_analysis import analyze_audio_match_enhanced
from scripts.agents import coach_agent, identify_sung_part_agent
from s3_handler import storage


def convert_to_serializable(obj):
    """Recursively convert numpy types to plain Python for JSON serialisation."""
    if isinstance(obj, dict):
        return {k: convert_to_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_serializable(i) for i in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


def cleanup_temp_files(user_audio_path, user_transcription_path):
    """Remove temporary per-request files from storage."""
    for path in (user_audio_path, user_transcription_path):
        if not path:
            continue
        try:
            if storage.file_exists(path):
                if storage.is_production:
                    storage.s3_client.delete_object(
                        Bucket=storage.bucket_name, Key=path
                    )
                    print(f"✅ Deleted from S3: {path}")
                else:
                    os.remove(path)
                    print(f"✅ Deleted locally: {path}")
        except Exception as e:
            print(f"⚠️ Could not delete {path}: {e}")


def _fuzzy_fallback(song_alignment, user_words):
    """Thin wrapper so identify_sung_part_agent can call the old matcher."""
    song_words = get_words_only(song_alignment)
    return identify_sung_part(song_words, user_words, song_alignment, True)


def process_user_audio(user_audio_path, gentle_json_path, reference_audio_path, file_id):
    """
    Full pipeline:
      1. Load song alignment from storage
      2. Transcribe user audio with Whisper
      3. Identify which segment of the song the user sang  ← now uses LLM
      4. Run pitch / DTW / audio analysis on that segment
      5. Generate coaching feedback with Groq
    """
    user_transcription_path = None

    try:
        # ── 1. Load song alignment ─────────────────────────────────────────────
        # Prefer local disk (covers songs processed before S3 migration, and
        # songs already in the local cache downloaded by song.py).
        # Fall back to S3 only when the file isn't present locally.
        if os.path.exists(gentle_json_path):
            with open(gentle_json_path, "r", encoding="utf-8") as f:
                gentle_alignment = json.load(f)
            print(f"📂 Loaded alignment from local: {gentle_json_path}")
        else:
            print(f"☁️  Alignment not local — downloading from S3: {gentle_json_path}")
            raw = storage.read_file(gentle_json_path)
            gentle_alignment = json.loads(raw) if isinstance(raw, str) else raw
        song_words = get_words_only(gentle_alignment)

        # ── 2. Transcribe user audio ───────────────────────────────────────────
        print("Transcribing user audio …")
        user_transcription_path = f"user_transcriptions/{file_id}_transcription.json"
        transcribe_with_whisper(user_audio_path, user_transcription_path)

        raw_trans = storage.read_file(user_transcription_path)
        user_alignment = json.loads(raw_trans) if isinstance(raw_trans, str) else raw_trans
        user_words = get_words_only(user_alignment["alignment"])
        print(f"User words: {user_words}")

        # ── 3. Extract pitch contours ──────────────────────────────────────────
        print("Extracting pitch contours …")
        user_pitch = extract_pitch_contour(user_audio_path)
        ref_pitch  = extract_pitch_contour(reference_audio_path)
        sr         = 16000
        hop_length = 512

        # ── 4. Identify sung segment (LLM-first, fuzzy fallback) ──────────────
        print("Identifying sung segment via LLM …")
        t0 = time.perf_counter()
        match = identify_sung_part_agent(
            song_alignment=gentle_alignment,
            user_words=user_words,
            fallback_fn=_fuzzy_fallback,
        )
        print(f"Segment identified in {time.perf_counter() - t0:.2f}s")

        if not match:
            return {"error": "Could not locate the sung segment in the song."}

        print(f"🎯 Matched segment: {match['start_time']:.2f}s – {match['end_time']:.2f}s")
        print(f"   Lyrics: {match['song_words_snippet']}")

        # ── 5. Audio analysis + coaching feedback ─────────────────────────────
        analysis = analyze_audio_match_enhanced(
            user_audio_path=user_audio_path,
            reference_audio_path=reference_audio_path,
            match=match,
            ref_pitch=ref_pitch,
            sr=sr,
            hop_length=hop_length,
        )

        feedback = coach_agent(analysis)

        # Persist analysis for debugging / history
        analysis_serializable = convert_to_serializable(analysis)
        storage.write_file(
            f"analysis_results_{int(time.time())}.json",
            json.dumps(analysis_serializable, indent=2),
        )

        return {"output": feedback, "voice_analysis": json.dumps(analysis_serializable, indent=2)}

    finally:
        cleanup_temp_files(None, user_transcription_path)


if __name__ == "__main__":
    process_user_audio(
        user_audio_path="user_vocals/t1.wav",
        gentle_json_path="songs/Somebody That I Used To Know | Gotye | Lyrics Video/alignment.json",
        reference_audio_path="songs/Somebody That I Used To Know | Gotye | Lyrics Video/vocals.wav",
        file_id="test",
    )
