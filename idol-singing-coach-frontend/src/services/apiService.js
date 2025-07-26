// API service for handling requests to the backend
class ApiService {
  constructor() {
    this.baseUrl = 'http://localhost:8000';
    this.abortController = null;
  }

  // Create a new abort controller for canceling requests
  createAbortController() {
    if (this.abortController) {
      this.abortController.abort();
    }
    this.abortController = new AbortController();
    return this.abortController;
  }

  // Analyze audio recording
  async analyzeAudio(audioBlob, songName) {
    const controller = this.createAbortController();
    
    try {
      const formData = new FormData();
      formData.append('song_name', songName);
      formData.append('audio_file', audioBlob, `recording_${Date.now()}.wav`);

      const response = await fetch(`${this.baseUrl}/user/analyze`, {
        method: 'POST',
        body: formData,
        signal: controller.signal
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Server error (${response.status}): ${errorText}`);
      }

      const result = await response.json();
      return result || "I've analyzed your recording. Keep practicing - you're doing great!";
    } catch (err) {
      if (err.name === 'AbortError') {
        console.log('Audio analysis request aborted');
        throw new Error('Request was cancelled');
      }
      throw err;
    }
  }

  // Analyze text message
 async analyzeText(user_text,chatId=null) {
  const controller = this.createAbortController();
  console.log('Sending text for analysis:', user_text);
  
  try {
    const response = await fetch(`${this.baseUrl}/user/analyze_text`, {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ 
        user_text ,
        chat_id:chatId
      }),
      signal: controller.signal
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`Server error (${response.status}): ${errorText}`);
      // Throw error instead of returning string to maintain consistent error handling
      throw new Error(`Server error (${response.status}): ${errorText}`);
    }

    const result = await response.json();
    console.log('Received analysis result:', result);
    
    // Return the result directly - let the calling code handle the structure
    return result;

  } catch (err) {
    console.error('Error in analyzeText:', err);
    
    if (err.name === 'AbortError') {
      console.log('Text analysis request aborted');
      throw new Error('Request was cancelled');
    }
    
    // Re-throw the error to be handled by the calling code
    throw err;
  }
}

  // Cancel any ongoing requests
  cancelRequests() {
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }
  }
}

// Create a singleton instance
const apiService = new ApiService();

export default apiService;