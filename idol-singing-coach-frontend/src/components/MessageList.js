import { useEffect, useRef } from 'react';

export default function MessageList({ messages, isProcessing }) {
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="messages-container">
      {messages.map((msg, idx) => (
        <div key={`${idx}-${msg.timestamp}`} className={`message-wrapper ${msg.sender}`}>
          <div className={`message ${msg.sender}`}>{msg.text}</div>
        </div>
      ))}
      {isProcessing && (
        <div className="recording-status">Analyzing your input...</div>
      )}
      <div ref={messagesEndRef} />
    </div>
  );
}