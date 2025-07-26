// Audio conversion utilities
class AudioConverter {
  constructor() {
    this.audioContext = null;
  }

  // Create or get audio context
  getAudioContext() {
    if (!this.audioContext) {
      this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
        sampleRate: 44100
      });
    }
    return this.audioContext;
  }

  // Convert audio to WAV format using Web Audio API
  async convertToWav(audioBlob) {
    try {
      // If it's already WAV, return as is
      if (audioBlob.type === 'audio/wav') {
        return audioBlob;
      }

      const audioContext = this.getAudioContext();

      // Convert blob to array buffer
      const arrayBuffer = await audioBlob.arrayBuffer();
      
      // Decode audio data
      const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
      
      // Convert to WAV
      const wavBuffer = this.audioBufferToWav(audioBuffer);
      
      return new Blob([wavBuffer], { type: 'audio/wav' });
    } catch (error) {
      console.error('Error converting to WAV:', error);
      // Return original blob if conversion fails
      return audioBlob;
    }
  }

  // Convert AudioBuffer to WAV format
  audioBufferToWav(audioBuffer) {
    const numChannels = audioBuffer.numberOfChannels;
    const sampleRate = audioBuffer.sampleRate;
    const format = 1; // PCM
    const bitDepth = 16;

    const bytesPerSample = bitDepth / 8;
    const blockAlign = numChannels * bytesPerSample;

    // Get audio data
    const audioData = [];
    for (let channel = 0; channel < numChannels; channel++) {
      audioData.push(audioBuffer.getChannelData(channel));
    }

    // Calculate buffer size
    const dataLength = audioBuffer.length * numChannels * bytesPerSample;
    const bufferLength = 44 + dataLength;
    const arrayBuffer = new ArrayBuffer(bufferLength);
    const view = new DataView(arrayBuffer);

    // Write WAV header
    const writeString = (offset, string) => {
      for (let i = 0; i < string.length; i++) {
        view.setUint8(offset + i, string.charCodeAt(i));
      }
    };

    writeString(0, 'RIFF');
    view.setUint32(4, bufferLength - 8, true);
    writeString(8, 'WAVE');
    writeString(12, 'fmt ');
    view.setUint32(16, 16, true); // PCM chunk size
    view.setUint16(20, format, true);
    view.setUint16(22, numChannels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * blockAlign, true);
    view.setUint16(32, blockAlign, true);
    view.setUint16(34, bitDepth, true);
    writeString(36, 'data');
    view.setUint32(40, dataLength, true);

    // Write audio data
    let offset = 44;
    for (let i = 0; i < audioBuffer.length; i++) {
      for (let channel = 0; channel < numChannels; channel++) {
        const sample = Math.max(-1, Math.min(1, audioData[channel][i]));
        const intSample = sample < 0 ? sample * 0x8000 : sample * 0x7FFF;
        view.setInt16(offset, intSample, true);
        offset += 2;
      }
    }

    return arrayBuffer;
  }

  // Clean up audio context
  async cleanup() {
    if (this.audioContext && this.audioContext.state !== 'closed') {
      try {
        await this.audioContext.close();
      } catch (err) {
        console.warn('Error closing audio context:', err);
      }
      this.audioContext = null;
    }
  }
}

export default AudioConverter;