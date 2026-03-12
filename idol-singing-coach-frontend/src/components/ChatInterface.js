'use client'

import { useState, useCallback, useEffect, useRef } from 'react';
import { useSession } from 'next-auth/react';
import { useAudioRecorder } from '../hooks/useAudioRecorder';
import apiService from '../services/apiService';
import ChatHeader from './ChatHeader';
import MessageList from './MessageList';
import InputControls from './InputControls';
import '../styles/ChatInterface.css';

export default function ChatInterface({ song = "Unknown Song", chatData = null, onChatUpdate }) {
  const [inputText, setInputText] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [chatId, setChatId] = useState(null);
  const [messages, setMessages] = useState([]);
  const { data: session } = useSession();
  const isSavingRef = useRef(false);
  

  useEffect(() => {
    if (chatData?.id && chatData?.messages) {
      console.log('Loading existing chat:', chatData.id);
      setChatId(chatData.id);

      const transformedMessages = chatData.messages.map(msg => {
        const hasDetailed = msg.detailedContent || msg.voice_analysis;
        return {
          ...msg,
          sender: msg.role || msg.sender,
          text: (msg.role === 'user' && hasDetailed)
            ? '🎵 Voice recording'
            : msg.content || msg.text
        };
      });

      setMessages(transformedMessages);
    } else {
      console.log('Creating new chat');
      setChatId(null);
      const welcomeMessage = {
        role: 'assistant',
        content: `Great choice! You're practicing "${song}". I'm here to help you improve your singing. You can record yourself singing or ask me questions about technique, breathing, or anything else related to your vocal practice.`,
        sender: 'assistant',
        text: `Great choice! You're practicing "${song}". I'm here to help you improve your singing. You can record yourself singing or ask me questions about technique, breathing, or anything else related to your vocal practice.`,
        timestamp: new Date().toISOString()
      };
      setMessages([welcomeMessage]);
    }
  }, [chatData?.id, song]);

  useEffect(() => {
    console.log('Messages for MessageList:', messages);
  }, [messages]);

  const {
    recording,
    recordingTime,
    micPermission,
    startRecording,
    stopRecording,
    cleanupRecording
  } = useAudioRecorder();

  const saveToDatabase = useCallback(async (messagesToSave, currentChatId) => {
    if (!session?.user?.email || isSavingRef.current) return currentChatId;
    isSavingRef.current = true;

    try {
      const isNewChat = !currentChatId;
      const method = isNewChat ? 'POST' : 'PUT';
      const url = isNewChat ? '/api/chats' : `/api/chats/${currentChatId}`;

      const response = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          song,
          messages: messagesToSave,
          userEmail: session.user.email,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        const savedChatId = data.chat._id;
        if (onChatUpdate) {
          onChatUpdate({
            id: savedChatId,
            song: data.chat.song,
            messages: messagesToSave,
            updatedAt: data.chat.updatedAt,
          });
        }
        return savedChatId;
      }
      return currentChatId;
    } catch (error) {
      console.error('Save error:', error);
      return currentChatId;
    } finally {
      isSavingRef.current = false;
    }
  }, [song, session?.user?.email, onChatUpdate]);

  // Batch-add multiple messages in a single state update + single DB save.
  // Use this instead of calling addMessage() twice in quick succession to avoid
  // the race condition where both calls see chatId=null and create two separate chats.
  const addMessages = useCallback((items) => {
    const now = Date.now();
    const newMessages = items.map((item, i) => ({
      role: item.role,
      content: item.content,
      sender: item.role,
      text: typeof item.content === 'string' ? item.content : JSON.stringify(item.content),
      timestamp: new Date(now + i).toISOString(),
      ...(item.metadata || {}),
    }));

    setMessages(prev => {
      const updated = [...prev, ...newMessages];
      saveToDatabase(updated, chatId).then(newChatId => {
        if (newChatId && newChatId !== chatId) setChatId(newChatId);
      }).catch(err => console.error('Failed to save messages:', err));
      return updated;
    });
  }, [chatId, saveToDatabase]);

  // Single-message add (used for text chat and error messages)
  const addMessage = useCallback((role, content, metadata = {}) => {
    const newMessage = {
      role,
      content,
      sender: role,
      text: typeof content === 'string' ? content : JSON.stringify(content),
      timestamp: new Date().toISOString(),
      ...metadata
    };
    
    // Add message immediately to state for instant UI update
    setMessages(prev => {
      const updated = [...prev, newMessage];
      // Save to database asynchronously without blocking UI
      saveToDatabase(updated, chatId).then(newChatId => {
        if (newChatId && newChatId !== chatId) {
          setChatId(newChatId);
        }
      }).catch(error => {
        console.error('Failed to save message:', error);
      });
      return updated;
    });
  }, [chatId, saveToDatabase]);

  const handleRecordingComplete = useCallback(async (audioBlob, errorMessage) => {
    if (errorMessage) {
      addMessage('assistant', errorMessage);
      return;
    }
    if (!audioBlob) return;

    setIsProcessing(true);
    try {
      const result = await apiService.analyzeAudio(audioBlob, song);

      // Extract coaching text from response
      let assistantResponse;
      if (typeof result === 'string') {
        assistantResponse = result;
      } else if (result.output) {
        assistantResponse = typeof result.output === 'string' ? result.output : JSON.stringify(result.output);
      } else if (result.response) {
        assistantResponse = result.response;
      } else {
        assistantResponse = JSON.stringify(result);
      }

      // Batch-add BOTH messages in one DB save:
      //  - user message carries the real analysis JSON (not the raw Blob)
      //    so the chatbot can retrieve it later via get_user_singing_data_tool
      //  - assistant message carries the coaching text
      addMessages([
        {
          role: 'user',
          content: '🎵 Voice recording',
          metadata: { voice_analysis: result.voice_analysis || null },
        },
        {
          role: 'assistant',
          content: assistantResponse,
        },
      ]);
    } catch (err) {
      console.error('Audio processing error:', err);
      addMessages([
        { role: 'user', content: '🎵 Voice recording' },
        { role: 'assistant', content: `There was an issue analyzing your recording: ${err.message}` },
      ]);
    } finally {
      setIsProcessing(false);
    }
  }, [song, addMessages]);

  const handleSendText = useCallback(async () => {
    if (!inputText.trim() || isProcessing || recording) return;
    
    const userMessage = inputText.trim();
    setInputText('');
    
    // Add user message immediately
    addMessage('user', userMessage);
    
    setIsProcessing(true);
    try {
      const result = await apiService.analyzeText(userMessage, chatId);
      
      // Handle different response formats from API
      let assistantResponse;
      if (typeof result === 'string') {
        assistantResponse = result;
      } else if (result.response) {
        assistantResponse = result.response;
      } else if (result.output) {
        assistantResponse = result.output;
      } else if (result.message) {
        assistantResponse = result.message;
      } else {
        assistantResponse = JSON.stringify(result);
      }
      
      addMessage('assistant', assistantResponse);
    } catch (err) {
      if (err.message !== 'Request was cancelled') {
        addMessage('assistant', `Issue processing your message: ${err.message}`);
      }
    } finally {
      setIsProcessing(false);
    }
  }, [inputText, isProcessing, recording, addMessage]);

  const handleStartRecording = useCallback(() => {
    startRecording(handleRecordingComplete);
  }, [startRecording, handleRecordingComplete]);

  return (
    <div className="chat-container">
      <ChatHeader song={song} chatId={chatId} />
      <MessageList messages={messages} isProcessing={isProcessing} />
      <InputControls
        inputText={inputText}
        setInputText={setInputText}
        recording={recording}
        recordingTime={recordingTime}
        micPermission={micPermission}
        isProcessing={isProcessing}
        onStartRecording={handleStartRecording}
        onStopRecording={stopRecording}
        onSendText={handleSendText}
      />
    </div>
  );
}