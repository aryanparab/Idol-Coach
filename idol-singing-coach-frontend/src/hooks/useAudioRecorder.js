import { useState, useRef, useCallback, useEffect } from 'react';
import AudioConverter from '../utils/audioConverter';

export function useAudioRecorder() {
  const [recording, setRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [micPermission, setMicPermission] = useState(null);

  const mediaRecorderRef = useRef(null);
  const audioStreamRef = useRef(null);
  const audioChunksRef = useRef([]);
  const timerRef = useRef(null);
  const isCleaningUpRef = useRef(false);
  const audioConverterRef = useRef(new AudioConverter());

  const checkMicPermission = useCallback(async () => {
    try {
      const result = await navigator.permissions.query({ name: 'microphone' });
      setMicPermission(result.state);
      result.onchange = () => setMicPermission(result.state);
    } catch {
      console.log('Permission API not supported');
    }
  }, []);

  const cleanupRecording = useCallback(async () => {
    if (isCleaningUpRef.current) return;
    isCleaningUpRef.current = true;

    // Clear timer
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }

    // Stop recording if active
    try {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
        await new Promise((resolve, reject) => {
          const timeout = setTimeout(() => reject(new Error('Stop timeout')), 3000);
          mediaRecorderRef.current.onstop = () => {
            clearTimeout(timeout);
            resolve();
          };
          mediaRecorderRef.current.stop();
        });
      }
    } catch (err) {
      console.warn('Error while stopping recorder:', err);
    }

    // Clean up audio stream
    if (audioStreamRef.current) {
      audioStreamRef.current.getTracks().forEach(track => {
        track.stop();
      });
      audioStreamRef.current = null;
    }

    // Clean up audio converter
    await audioConverterRef.current.cleanup();

    // Reset refs
    mediaRecorderRef.current = null;
    audioChunksRef.current = [];
    
    // Reset state
    setRecording(false);
    setRecordingTime(0);
    
    isCleaningUpRef.current = false;
  }, []);

  const startRecording = useCallback(async (onRecordingComplete) => {
    if (recording || isCleaningUpRef.current) return;

    // Cleanup any existing recording first
    await cleanupRecording();
    
    // Small delay to ensure cleanup is complete
    await new Promise(resolve => setTimeout(resolve, 200));

    try {
      // Request fresh audio stream with high quality settings
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 44100,
          channelCount: 1 // Mono for better librosa compatibility
        } 
      });
      
      audioStreamRef.current = stream;

      // Try to use WAV format first, then fallback to supported formats
      let mimeType = 'audio/wav';
      if (!MediaRecorder.isTypeSupported('audio/wav')) {
        console.log('WAV not supported, using fallback format');
        if (MediaRecorder.isTypeSupported('audio/webm;codecs=pcm')) {
          mimeType = 'audio/webm;codecs=pcm';
        } else if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
          mimeType = 'audio/webm;codecs=opus';
        } else if (MediaRecorder.isTypeSupported('audio/webm')) {
          mimeType = 'audio/webm';
        } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
          mimeType = 'audio/mp4';
        } else {
          // Use default
          mimeType = '';
        }
      }

      const mediaRecorder = new MediaRecorder(stream, { 
        mimeType: mimeType,
        audioBitsPerSecond: 128000
      });
      
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        if (audioChunksRef.current.length === 0) {
          onRecordingComplete(null, "I didn't catch any audio. Please make sure your microphone is working and try recording again.");
          await cleanupRecording();
          return;
        }

        try {
          // Create blob from recorded chunks
          const originalBlob = new Blob([...audioChunksRef.current], { 
            type: mediaRecorder.mimeType || 'audio/webm' 
          });
          
          // Validate audio blob
          if (originalBlob.size === 0) {
            throw new Error('Empty audio recording');
          }

          // Convert to WAV format for librosa compatibility
          console.log('Converting audio to WAV format...');
          const wavBlob = await audioConverterRef.current.convertToWav(originalBlob);
          
          console.log(`Audio converted: ${originalBlob.type} -> ${wavBlob.type}, Size: ${wavBlob.size} bytes`);

          onRecordingComplete(wavBlob, null);
        } catch (error) {
          console.error('Audio processing error:', error);
          onRecordingComplete(null, `There was an issue processing your recording: ${error.message}. Please try again.`);
        } finally {
          await cleanupRecording();
        }
      };

      mediaRecorder.onerror = (event) => {
        console.error('MediaRecorder error:', event.error);
        onRecordingComplete(null, "There was an issue with the recording. Please check your microphone and try again.");
        cleanupRecording();
      };

      // Start recording
      mediaRecorder.start(1000); // Collect data every second
      setRecording(true);
      setRecordingTime(0);

      // Start timer
      timerRef.current = setInterval(() => {
        setRecordingTime((time) => {
          // Auto-stop after 60 seconds
          if (time >= 59) {
            stopRecording();
            return 60;
          }
          return time + 1;
        });
      }, 1000);

    } catch (err) {
      console.error('Recording start error:', err);
      setMicPermission('denied');
      onRecordingComplete(null, "I need microphone access to help analyze your singing. Please allow microphone access in your browser settings and refresh the page.");
      await cleanupRecording();
    }
  }, [recording, cleanupRecording]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
  }, []);

  useEffect(() => {
    checkMicPermission();
    return () => {
      cleanupRecording();
    };
  }, [checkMicPermission, cleanupRecording]);

  return {
    recording,
    recordingTime,
    micPermission,
    startRecording,
    stopRecording,
    cleanupRecording
  };
}