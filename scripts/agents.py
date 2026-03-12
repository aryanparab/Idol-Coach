import os
from dotenv import load_dotenv
import re
import json
from typing import List, Dict, Optional
from groq import Groq
from pymongo import MongoClient
from bson import ObjectId

load_dotenv()

# ── Groq client ────────────────────────────────────────────────────────────────
_groq = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"


def _chat(system: str, user: str, max_tokens: int = 1024) -> str:
    """Single helper — calls Groq and returns the text response."""
    response = _groq.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        max_tokens=max_tokens,
        temperature=0.7,
    )
    return response.choices[0].message.content


# ── Agent functions ────────────────────────────────────────────────────────────

def extract_title_artist(youtube_title: str):
    system = (
        "You extract song titles and artist names from YouTube video titles. "
        "Respond only with the requested fields, no extra text."
    )
    user = f"""Extract the song title and artist(s) from this YouTube video title:
"{youtube_title}"

Respond in this exact format:
  "title": "Song Name",
  "artist": "Artist Name"
"""
    text = _chat(system, user, max_tokens=100)
    print(text)
    title  = re.search(r'"title":\s*"([^"]+)"', text).group(1)
    artist = re.search(r'"artist":\s*"([^"]+)"', text).group(1)
    return title, artist


def _score_label(score: float) -> str:
    """Translate a 0–1 score into a human-readable label for the LLM."""
    if score >= 0.85: return "excellent"
    if score >= 0.65: return "good"
    if score >= 0.45: return "developing"
    if score >= 0.25: return "needs attention"
    return "a real focus area"


def _format_word_issues(granular: Optional[Dict]) -> str:
    """
    Format per-word observations for the LLM prompt.

    For pitch issues we now have BOTH sides (user note + reference note),
    so the LLM can say "you sang a G but it wants an A" rather than
    the abstract "48 cents flat".

    Format per line:
      "care": you sang ~G3, should be ~A3 (half-step flat); tone slightly bright
      "love":  right on pitch (~E4); sounded great
    """
    if not granular:
        return ""
    entries = granular.get("detailed_feedback", [])
    lines = []
    for entry in entries[:6]:
        word = entry.get("word", "")
        if not word:
            continue
        feedback_items = entry.get("feedback", [])
        # Strip any leftover emoji/symbol prefixes for clean LLM context
        clean = [re.sub(r'^[^\w\s~"]+\s*', '', fb).strip() for fb in feedback_items[:4]]
        clean = [c for c in clean if c]
        summary = "; ".join(clean) if clean else "sounded good"
        lines.append(f'  "{word}": {summary}')
    return "\n".join(lines) if lines else ""


def coach_agent(analysis: dict) -> str:
    ts   = analysis.get("technical_summary", {})
    ba   = analysis.get("breath_analysis",   {})
    dtw  = analysis.get("dtw_analysis",      {})
    lyrics = analysis.get("matched_lyrics", "")
    word_issues = _format_word_issues(analysis.get("granular_feedback"))

    # Compute plain-English interpretations of key scores
    pitch_lbl   = _score_label(ts.get("pitch_accuracy",  0))
    stable_lbl  = _score_label(ts.get("vocal_stability", 0))
    breath_lbl  = _score_label(ts.get("breath_support",  0))
    tone_lbl    = _score_label(ts.get("voice_quality",   0))
    expr_lbl    = _score_label(ts.get("expression_level",0))
    dtw_lbl     = _score_label(dtw.get("alignment_quality", 0))

    breath_note = (
        "You're not using breath support at all right now — your air ran out before the phrase did."
        if ts.get("breath_support", 0) < 0.15
        else f"Breath support is {breath_lbl}."
    )

    system = """\
You are a sharp, warm vocal coach who just listened to a student sing. \
You speak in plain conversational English — no bullet points, no markdown, no score numbers. \
Your feedback always does three things:
1. Open with something SPECIFIC you noticed about how they sounded on a particular word or moment — \
   quote the exact lyric word(s) using double quotes so the student knows exactly what you're talking about.
2. Identify the ONE or TWO most important things to fix, explaining what it sounds/feels like \
   (not abstract labels), and tie each point back to a specific word or phrase they sang.
3. Close with ONE concrete drill or technique they can try RIGHT NOW — \
   make it vivid and specific, not generic advice.
Write 2–3 short paragraphs, under 200 words. Sound like a mentor who cares, not a report.\
"""

    user = f"""\
The student just sang this lyric excerpt: "{lyrics}"

Here is what the analysis detected:
- Tone/voice quality: {tone_lbl}
- Pitch accuracy: {pitch_lbl}
- Pitch stability (staying on note): {stable_lbl}
- {breath_note}
- Expression/dynamics: {expr_lbl}
- Rhythmic alignment with the original: {dtw_lbl}
- Breaths taken: {ba.get('breath_count', 0)} (avg {ba.get('average_breath_duration', 0):.1f}s each)

Word-by-word observations (use these to quote specific moments in your response):
{word_issues if word_issues else '  No per-word data — rely on the overall scores above.'}

Write your coaching response now. \
Quote at least one specific word from the lyrics when praising and at least one when correcting. \
Do NOT recite numbers or label names. \
Plain text only, 2–3 paragraphs.\
"""
    return _chat(system, user, max_tokens=400)


# ── MongoDB (for chatbot agent) ────────────────────────────────────────────────
_mongo_client    = MongoClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017"))
_db              = _mongo_client[os.getenv("MONGODB_DB")]
chats_collection = _db.chats


def get_chat_history_tool(chat_id: str, limit: int = 10) -> str:
    try:
        if not chat_id:
            return "No chat ID provided"
        chat = chats_collection.find_one({"_id": ObjectId(chat_id)})
        if not chat:
            return "Chat not found"
        messages = chat.get("messages", [])
        recent = messages[-limit:] if len(messages) > limit else messages
        history = []
        for msg in recent:
            if msg.get("content") == "🎵 Voice recording":
                continue
            history.append(
                f"{msg.get('role','unknown')} ({msg.get('timestamp','')}): {msg.get('content','')}"
            )
        return "\n".join(history) if history else "No text messages found in recent history"
    except Exception as e:
        return f"Error accessing chat history: {e}"


def get_user_singing_data_tool(chat_id: str) -> str:
    try:
        if not chat_id:
            return "No chat ID provided"
        chat = chats_collection.find_one({"_id": ObjectId(chat_id)})
        if not chat:
            return "No singing data found"
        messages = chat.get("messages", [])
        recordings = []
        for i, msg in enumerate(messages):
            if (msg.get("role") == "user"
                    and msg.get("content") == "🎵 Voice recording"
                    and "voice_analysis" in msg):
                assistant_feedback = ""
                if i + 1 < len(messages) and messages[i + 1].get("role") == "assistant":
                    assistant_feedback = messages[i + 1].get("content", "")

                # Parse the stored analysis JSON to extract key fields
                raw_analysis = msg.get("voice_analysis") or {}
                if isinstance(raw_analysis, str):
                    try:
                        raw_analysis = json.loads(raw_analysis)
                    except Exception:
                        raw_analysis = {}

                ts    = raw_analysis.get("technical_summary", {})
                lyrics = raw_analysis.get("matched_lyrics", "")

                # Build a human-readable summary of what happened in this recording
                rec_lines = [f'They sang: "{lyrics}"' if lyrics else "Lyrics not captured"]
                if ts:
                    interesting = []
                    tone = ts.get("voice_quality", None)
                    pitch = ts.get("pitch_accuracy", None)
                    stab  = ts.get("vocal_stability", None)
                    breath = ts.get("breath_support", None)
                    if tone  is not None: interesting.append(f"tone {_score_label(tone)}")
                    if pitch is not None: interesting.append(f"pitch accuracy {_score_label(pitch)}")
                    if stab  is not None: interesting.append(f"stability {_score_label(stab)}")
                    if breath is not None: interesting.append(f"breath support {_score_label(breath)}")
                    if interesting:
                        rec_lines.append("Scores: " + ", ".join(interesting))

                if assistant_feedback:
                    rec_lines.append(f"Feedback given: {assistant_feedback[:300]}")

                recordings.append({
                    "timestamp": msg.get("timestamp", "Unknown time"),
                    "summary":   "\n  ".join(rec_lines),
                })

        if not recordings:
            return "No voice recordings found in this chat yet."

        out = [f"Found {len(recordings)} recording(s) in this session:\n"]
        for i, rec in enumerate(recordings[-3:], 1):
            out.append(f"Recording {i} ({rec['timestamp']}):\n  {rec['summary']}\n")
        return "\n".join(out)
    except Exception as e:
        return f"Error accessing singing data: {e}"


AVAILABLE_TOOLS_chatbot_agent = [
    {
        "name": "get_chat_history",
        "description": (
            "Get recent text conversation history for context. Use when user refers to "
            "previous messages, asks 'what did we discuss', or needs conversational "
            "continuity. Excludes voice recordings."
        ),
        "parameters": {
            "chat_id": "string - The current chat ID",
            "limit": "integer - Number of recent messages to retrieve (default: 10)",
        },
    },
    {
        "name": "get_user_singing_data",
        "description": (
            "Get user's singing practice data including voice recordings, analysis "
            "results, and feedback given. Use when discussing singing progress, "
            "technique improvement, or when user asks about their performance."
        ),
        "parameters": {
            "chat_id": "string - The current chat ID",
        },
    },
]


def execute_tool(tool_name: str, chat_id: str, **kwargs) -> str:
    if tool_name == "get_chat_history":
        return get_chat_history_tool(chat_id, kwargs.get("limit", 10))
    elif tool_name == "get_user_singing_data":
        return get_user_singing_data_tool(chat_id)
    return f"Unknown tool: {tool_name}"


def chatbot_agent(prompt: str, chat_id: str) -> str:
    system = f"""\
You are an experienced, encouraging vocal coach having a real conversation with a student. \
You speak plainly and personally — no bullet points, no markdown, no score numbers. \
When the student asks about their singing, always tie your advice back to specific lyric \
words or moments from their recordings if you have access to them. \
If you don't have data yet, give practical, vivid technique advice as if you're in the room together.

You have two tools available:

TOOL: get_chat_history
  Use when: the student refers to something said earlier, asks "what did we discuss", or needs conversational continuity.
  Call as: TOOL_CALL: get_chat_history(chat_id="{chat_id}", limit=8)

TOOL: get_user_singing_data
  Use when: the student asks about their progress, their recordings, what they need to work on, or how they've been doing.
  Call as: TOOL_CALL: get_user_singing_data(chat_id="{chat_id}")

Rules:
- Only call ONE tool per response, and only when the answer genuinely requires it.
- For general technique questions (breathing, vowels, posture, etc.) answer directly — no tool needed.
- When you DO use tool data, weave it into natural coach language. \
  Quote specific lyric words from their recordings when giving feedback. \
  Never dump raw data at the student.
- Plain text only. Sound like a mentor, not a system.\
"""

    try:
        response_text = _chat(system, prompt, max_tokens=600)
        print(f"[chatbot_agent] first pass:\n{response_text}")

        if "TOOL_CALL" in response_text:
            tool_line = next(
                (line for line in response_text.split("\n") if "TOOL_CALL" in line), ""
            )
            tool_call = tool_line.replace("TOOL_CALL:", "").strip()
            if "(" in tool_call:
                tool_name   = tool_call.split("(")[0].strip()
                tool_result = execute_tool(tool_name, chat_id)
                print(f"[chatbot_agent] tool={tool_name}, result snippet: {tool_result[:200]}")

                followup = f"""\
The student asked: {prompt}

Here is the data you retrieved:
{tool_result}

Now write your coaching response. \
Quote specific lyric words from their recordings where relevant. \
Plain conversational text, 2–3 short paragraphs, no markdown, no numbers.\
"""
                final = _chat(system, followup, max_tokens=600)
                print(f"[chatbot_agent] final response:\n{final}")
                return final

        return response_text

    except Exception as e:
        print(f"[chatbot_agent] error: {e}")
        fallback = _groq.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
        )
        return fallback.choices[0].message.content


# ── LLM-based lyric segment identifier ────────────────────────────────────────

def _format_alignment_table(alignment: List[Dict]) -> str:
    """
    Compact representation of the gentle alignment for the LLM.
    Format: idx | word | start_s | end_s
    Keeps tokens low while preserving all timing info.
    """
    lines = ["idx | word | start | end"]
    for i, entry in enumerate(alignment):
        word  = entry.get("word", "").strip()
        start = entry.get("start", 0)
        end   = entry.get("end", 0)
        if word:
            lines.append(f"{i} | {word} | {start:.2f} | {end:.2f}")
    return "\n".join(lines)


def identify_sung_part_agent(
    song_alignment: List[Dict],
    user_words: List[str],
    fallback_fn=None,
) -> Optional[Dict]:
    """
    Use Groq to find which part of the song the user sang.

    Replaces the fuzzy sliding-window matcher.  Returns a dict with the same
    shape as identify_sung_part() so the rest of the pipeline is unchanged:
        {
            "found_match": True,
            "start_time":  float,
            "end_time":    float,
            "song_words_snippet": str,   # matched song lyrics
            "confidence":  float,
        }

    Falls back to `fallback_fn(song_alignment, user_words)` if the LLM fails
    or returns unparseable JSON.
    """
    alignment_table = _format_alignment_table(song_alignment)
    user_text       = " ".join(user_words)

    system = (
        "You are a music analysis assistant. "
        "Given a word-level song alignment and a user's sung transcription, "
        "identify exactly which segment of the song the user is singing. "
        "Account for singing variations: omitted words, slurred syllables, "
        "repeated phrases, filler sounds (uh, ah, mmm), and pronunciation differences. "
        "Respond ONLY with a JSON object — no explanation, no markdown."
    )

    user_prompt = f"""Song alignment (tab-separated: idx | word | start_s | end_s):
{alignment_table}

The user sang (Whisper transcription):
\"{user_text}\"

Find the contiguous segment in the song alignment that best matches what the user sang.
Return this exact JSON and nothing else:
{{
  "start_idx": <integer index of first matching word>,
  "end_idx":   <integer index of last matching word (inclusive)>,
  "start_time": <float seconds>,
  "end_time":   <float seconds>,
  "matched_lyrics": "<the song words from start_idx to end_idx, space-joined>",
  "confidence": <float 0.0-1.0>
}}"""

    try:
        raw = _chat(system, user_prompt, max_tokens=256)
        print(f"[identify_sung_part_agent] raw response: {raw}")

        # Extract JSON even if the model wraps it in backticks
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not json_match:
            raise ValueError("No JSON object found in LLM response")

        result = json.loads(json_match.group())

        start_idx = int(result["start_idx"])
        end_idx   = int(result["end_idx"])

        # Clamp to valid range
        start_idx = max(0, min(start_idx, len(song_alignment) - 1))
        end_idx   = max(start_idx, min(end_idx, len(song_alignment) - 1))

        # Re-derive times directly from alignment (don't trust LLM floats blindly)
        start_time = song_alignment[start_idx].get("start", result.get("start_time", 0))
        end_time   = song_alignment[end_idx].get("end",   result.get("end_time",   0))
        snippet    = result.get(
            "matched_lyrics",
            " ".join(e.get("word", "") for e in song_alignment[start_idx:end_idx + 1])
        )

        print(f"[identify_sung_part_agent] matched '{snippet}' @ {start_time:.2f}s–{end_time:.2f}s "
              f"(confidence {result.get('confidence', '?')})")

        return {
            "found_match":         True,
            "start_time":          float(start_time),
            "end_time":            float(end_time),
            "duration_seconds":    float(end_time) - float(start_time),
            "song_words_snippet":  snippet,
            "user_input":          user_text,
            "confidence":          float(result.get("confidence", 0.8)),
            "timing_data":         song_alignment[start_idx:end_idx + 1],
            "match_details": {
                "method":        "llm",
                "word_indices":  (start_idx, end_idx),
                "was_expanded":  False,
            },
        }

    except Exception as e:
        print(f"[identify_sung_part_agent] LLM match failed: {e}")
        if fallback_fn:
            print("[identify_sung_part_agent] falling back to fuzzy matcher")
            return fallback_fn(song_alignment, user_words)
        return None
