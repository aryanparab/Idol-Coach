import google.generativeai as genai
import os
from dotenv import load_dotenv
import re
from pymongo import MongoClient
import json
from typing import Optional
from bson import ObjectId


load_dotenv() 

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = "gemini-2.0-flash"

def extract_title_artist(youtube_title):
    prompt = f"""
    Extract the song title and artist(s) from this YouTube video title:
    "{youtube_title}"

    Respond in  format like this :
   
      "title": "Song Name",
      "artist": "Artist Name"

    """
    response = genai.GenerativeModel(model).generate_content(prompt)
    text = response.text
    print(text)
    title, artist = re.search(r'"title":\s*"([^"]+)"', text).group(1), re.search(r'"artist":\s*"([^"]+)"', text).group(1)    

    return title,artist


def coach_agent(analysis):
    
    # AI Singing Coach Prompt Template
    prompt = f"""
You are a professional vocal coach giving constructive, friendly feedback to a student who just sang a snippet of a song.

Here is the context of their performance:

- **Lyrics sung**: "{analysis['matched_lyrics']}" from {analysis['start_time']}s to {analysis['end_time']}s.
- **Coaching level**: {analysis['coaching_level']}

**Technical Summary**:
- Pitch Accuracy: {analysis['technical_summary']['pitch_accuracy']:.2f}
- Vocal Stability: {analysis['technical_summary']['vocal_stability']:.2f}
- Breath Support: {analysis['technical_summary']['breath_support']:.2f}
- Expression Level: {analysis['technical_summary']['expression_level']:.2f}
- Vibrato Quality: {analysis['technical_summary']['vibrato_quality']:.2f}
- Onset Quality: {analysis['technical_summary']['onset_quality']:.2f}
- Voice Quality: {analysis['technical_summary']['voice_quality']:.2f}
- Dynamic Range: {analysis['technical_summary']['dynamic_range']:.2f}

**Breath Analysis**:
- Breaths Taken: {analysis['breath_analysis']['breath_count']}
- Avg Breath Duration: {analysis['breath_analysis']['average_breath_duration']:.2f}s
- Breath Efficiency: {analysis['breath_analysis']['breath_efficiency']:.2f}

**Alignment Quality (DTW)**: {analysis['dtw_analysis']['alignment_quality']:.2f}

Now, using the detailed **granular feedback** below, please give the student concise coaching:
- Focus mostly on **important word-level feedback** from the performance.
- Mention strengths and areas to improve.
- Be specific but not too long.
- Be friendly, encouraging, and informative.

Granular Feedback:
{analysis['granular_feedback']}

Please begin your response with an encouraging statement and  matched_lyrics : {analysis['matched_lyrics']}
Keep your reply under 150 words
"""

    response = genai.GenerativeModel(model).generate_content(prompt)
    text = response.text
   
    return text


client = MongoClient(os.getenv('MONGODB_URI', 'mongodb://localhost:27017'))
db = client[os.getenv("MONGODB_DB")]  # Replace with your database name
chats_collection = db.chats


    
def get_chat_history_tool(chat_id:str,limit:int =10)->str:
    try:
        
        if not chat_id:
            return "No chat ID Provided"
       
        obj_id = ObjectId(chat_id)
        chat = chats_collection.find_one({"_id":obj_id})
        if not chat :
            return "Chat not found"

        messages = chat.get('messages',[])
        recent_messages = messages[-limit:] if len(messages) > limit else messages
        history = []
        for msg in recent_messages:
            role = msg.get('role','unknown')
            content = msg.get('content','')
            timestamp = msg.get('timestamp','')
            if content =="🎵 Voice recording":
                continue
            history.append(f"{role} ({timestamp}): {content}") 
        return "\n".join(history) if history else "No text Messages found in recent history"

    except Exception as e:
        return f"Error accessing chat history: {str(e)}"

def get_user_singing_data_tool(chat_id:str)-> str:
    try:
        
        if not chat_id:
            return "No chat ID provided"
        
        obj_id = ObjectId(chat_id)
        chat = chats_collection.find_one({"_id": obj_id})
        if not chat:
           
            return "No singing data found"

        # Extract voice analysis data from messages
        voice_recordings = []
        messages = chat.get('messages', [])
        
        for i, msg in enumerate(messages):
            # Look for user messages with voice_analysis
            if (msg.get('role') == 'user' and 
                msg.get('content') == '🎵 Voice recording' and 
                'voice_analysis' in msg):
                
                timestamp = msg.get('timestamp', 'Unknown time')
                voice_analysis = msg.get('voice_analysis', {})
                
                # Get the corresponding assistant response (usually the next message)
                assistant_response = ""
                if i + 1 < len(messages) and messages[i + 1].get('role') == 'assistant':
                    assistant_response = messages[i + 1].get('content', '')
                
                voice_recordings.append({
                    'timestamp': timestamp,
                    'analysis': voice_analysis,
                    'feedback': assistant_response[:200] + "..." if len(assistant_response) > 200 else assistant_response
                })
        
        if not voice_recordings:
            return "No voice recordings found in this chat"
        
        # Format the data for LLM
        summary = f"Found {len(voice_recordings)} voice recordings:\n\n"
        for i, recording in enumerate(voice_recordings[-3:], 1):  # Last 3 recordings
            summary += f"Recording {i} ({recording['timestamp']}):\n"
            if recording['analysis']:
                summary += f"Analysis: {str(recording['analysis'])}\n"
            if recording['feedback']:
                summary += f"Feedback given: {recording['feedback']}\n"
            summary += "\n"
        
        return summary
        
    except Exception as e:
        return f"Error accessing singing data: {str(e)}"

AVAILABLE_TOOLS_chatbot_agent = [
    {
        "name":"get_chat_history",
        "description":"Get recent text conversation history for context. Use when user refers to previous messages, asks 'what did we discuss', or needs conversational continuity. Excludes voice recordings.",
        "parameters": {
            "chat_id": "string - The current chat ID",
            "limit": "integer - Number of recent messages to retrieve (default: 10)"
        }
    },
    {
        "name": "get_user_singing_data", 
        "description": "Get user's singing practice data including voice recordings, analysis results, and feedback given. Use when discussing singing progress, technique improvement, comparing recordings, or when user asks about their performance.",
        "parameters": {
            "chat_id": "string - The current chat ID"
        }
    }
]    

def execute_tool(tool_name:str,chat_id:str,**kwargs)-> str:
    
    if tool_name=="get_chat_history":
        limit=kwargs.get('limit',10)
        return get_chat_history_tool(chat_id,limit)
    elif tool_name=="get_user_singing_data":
       
        return get_user_singing_data_tool(chat_id)
    else:
        return f"Unknown tool : {tool_name}"
def chatbot_agent(prompt,chat_id):
    system_prompt = f"""You are a helpful singing coach assistant. You can access additional information using these tools when needed:

Available Tools:
{json.dumps(AVAILABLE_TOOLS_chatbot_agent, indent=2)}

To use a tool, respond with: TOOL_CALL: tool_name(parameters)
For example: TOOL_CALL: get_chat_history(chat_id="{chat_id}", limit=5)

Only use tools when the user's question requires historical context or singing data. For general singing advice, respond directly without tools.

User's message: {prompt}
"""
    try:
        response = genai.GenerativeModel(model).generate_content(system_prompt)
        response_text = response.text
        print(response_text)
        if "TOOL_CALL" in response_text:
            tool_line = [line for line in response_text.split("\n") if 'TOOL_CALL' in line][0]
            tool_call = tool_line.replace('TOOL_CALL','').strip()
            if "(" in tool_call:
                tool_name = tool_call.split("(")[0].strip()
                
                tool_result = execute_tool(tool_name.split(":")[1].strip(),chat_id)
                
                enhanced_prompt = f"""Based on the following information, please provide a helpful response:

Original user message: {prompt}

Retrieved data: {tool_result}

Please provide a natural, helpful response as a singing coach."""
                
                final_response = genai.GenerativeModel(model).generate_content(enhanced_prompt)
                print("This is final response:",final_response.text)
            return final_response.text
        return response_text
    except Exception as e:
        print(f"Error in chatbot_agent: {e}")
        fallback_response = genai.GenerativeModel(model).generate_content(prompt)
        return fallback_response.text
