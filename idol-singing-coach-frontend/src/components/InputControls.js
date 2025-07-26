import { useEffect, useRef, useCallback } from 'react';
import { Mic, Send, Square } from 'lucide-react';

export default function InputControls({ 
  inputText, 
  setInputText, 
  recording, 
  recordingTime,
  micPermission,
  isProcessing,
  onStartRecording,
  onStopRecording,
  onSendText 
}) {
  const textareaRef = useRef(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 120) + 'px';
    }
  }, [inputText]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSendText();
    }
  }, [onSendText]);

  return (
    <div className="input-section">
      {recording && (
        <div className="recording-status">
          <div className="recording-dot"></div>
          Recording {Math.floor(recordingTime / 60)}:{String(recordingTime % 60).padStart(2, '0')}
        </div>
      )}
      {micPermission === 'denied' && (
        <div className="permission-warning">
          🎤 Microphone access is needed. Please enable it and refresh.
        </div>
      )}
      <div className="input-controls">
        <div className="textarea-wrapper">
          <textarea
            ref={textareaRef}
            className="message-input"
            rows={1}
            placeholder="Ask something or sing!"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={recording || isProcessing}
          />
        </div>
        <button
          onClick={recording ? onStopRecording : onStartRecording}
          className={`control-button mic-button ${recording ? 'recording' : ''}`}
          disabled={isProcessing}
        >
          {recording ? <Square size={20} /> : <Mic size={20} />}
        </button>
        <button
          onClick={onSendText}

          className="control-button send-button"
          disabled={!inputText.trim() || recording || isProcessing}
        >
          <Send size={20} />
        </button>
      </div>
    </div>
  );
}