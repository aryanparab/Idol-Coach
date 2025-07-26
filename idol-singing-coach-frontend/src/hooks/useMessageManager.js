import { useState, useCallback } from 'react';

export function useMessageManager(initialMessage = null) {
  const [messages, setMessages] = useState(() => {
    if (initialMessage) {
      return [{
        role: 'assistant',
        content: initialMessage,
        timestamp: new Date().toISOString(),
        id: Date.now()
      }];
    }
    return [];
  });

  const addMessage = useCallback((role, content) => {
    const message = {
      role,
      content,
      timestamp: new Date().toISOString(),
      id: Date.now() + Math.random() // Ensure uniqueness
    };

    setMessages(prev => [...prev, message]);
    return message;
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
  }, []);

  const updateMessage = useCallback((messageId, updates) => {
    setMessages(prev => 
      prev.map(msg => 
        msg.id === messageId 
          ? { ...msg, ...updates }
          : msg
      )
    );
  }, []);

  const removeMessage = useCallback((messageId) => {
    setMessages(prev => prev.filter(msg => msg.id !== messageId));
  }, []);

  return {
    messages,
    setMessages,
    addMessage,
    clearMessages,
    updateMessage,
    removeMessage
  };
}