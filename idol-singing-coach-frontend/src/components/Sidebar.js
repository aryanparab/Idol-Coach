'use client'

import { useState, useEffect } from 'react'
import { ChevronLeft, ChevronRight, Music, Clock, Trash2, Plus } from 'lucide-react'
import { useSession } from 'next-auth/react'
import Link from 'next/link'
import "../styles/Sidebar.css"

export default function Sidebar({ selectedSong, onSelectChat, onNewChat }) {
  const [open, setOpen] = useState(true)
  const [chats, setChats] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedChatId, setSelectedChatId] = useState(null)
  const { data: session } = useSession()

  // Load chats from MongoDB
  useEffect(() => {
    if (session?.user?.email) {
      loadChats()
    }
  }, [session])

  const loadChats = async () => {
    try {
      const response = await fetch('/api/chats', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      })
      
      if (response.ok) {
        const data = await response.json()
        setChats(data.chats || [])
      }
    } catch (error) {
      console.error('Error loading chats:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSelectChat = async (chat) => {
    try {
      const response = await fetch(`/api/chats/${chat._id}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      })
      
      if (response.ok) {
        const data = await response.json()
        setSelectedChatId(chat._id)
        onSelectChat({
          id: chat._id,
          song: chat.song,
          messages: data.chat.messages || []
        })
      }
    } catch (error) {
      console.error('Error loading chat:', error)
    }
  }

  const handleDeleteChat = async (chatId, event) => {
    event.stopPropagation()
    
    if (!confirm('Are you sure you want to delete this chat?')) {
      return
    }

    try {
      const response = await fetch(`/api/chats/${chatId}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
      })
      
      if (response.ok) {
        setChats(chats.filter(chat => chat._id !== chatId))
        // If the deleted chat was selected, clear selection
        if (selectedChatId === chatId) {
          setSelectedChatId(null)
          onNewChat()
        }
      }
    } catch (error) {
      console.error('Error deleting chat:', error)
    }
  }

  const handleNewChat = () => {
    setSelectedChatId(null)
    onNewChat()
  }

  const formatDate = (dateString) => {
    const date = new Date(dateString)
    const now = new Date()
    const diffTime = Math.abs(now - date)
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))
    
    if (diffDays === 1) return 'Today'
    if (diffDays === 2) return 'Yesterday'
    if (diffDays <= 7) return `${diffDays - 1} days ago`
    return date.toLocaleDateString()
  }

  if (!session) return null

  return (
    <div className={`sidebar ${!open ? 'collapsed' : ''}`}>
      <div className="sidebar-header">
        <button onClick={() => setOpen(!open)} className="toggle-button">
          {open ? <ChevronLeft size={20} /> : <ChevronRight size={20} />}
        </button>
        {open && (
          <div className="header-content">
            <Link href="/" className="sidebar-logo">
              <Music size={20} />
              <span>IDOL-COACH</span>
            </Link>
            <button onClick={handleNewChat} className="new-chat-button">
              <Plus size={16} />
              New Session
            </button>
          </div>
        )}
      </div>

      {open && (
        <div className="sidebar-content">
          {loading ? (
            <div className="loading-chats">Loading sessions...</div>
          ) : chats.length > 0 ? (
            <>
              <div className="section-title">Practice Sessions</div>
              <ul className="chat-list">
                {chats.map((chat) => (
                  <li 
                    key={chat._id} 
                    className={`chat-item ${selectedChatId === chat._id ? 'selected' : ''}`}
                  >
                   <button className="chat-button" onClick={() => handleSelectChat(chat)}>
  <div className="chat-info"> {chat.song }</div>
  <span
    role="button"
    tabIndex={0}
    className="delete-button"
    onClick={(e) => {
      e.stopPropagation()
      handleDeleteChat(chat._id, e)
    }}
    onKeyDown={(e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault()
        e.stopPropagation()
        handleDeleteChat(chat._id, e)
      }
    }}
    title="Delete chat"
  >
    <Trash2 size={14} />
  </span>
</button>

                  </li>
                ))}
              </ul>
            </>
          ) : (
            <div className="empty-state">
              <Music size={32} className="empty-icon" />
              <p>No sessions yet</p>
              <p className="empty-subtitle">Start practicing to see your sessions here</p>
            </div>
          )}
        </div>
      )}

      {!open && (
        <div className="collapsed-indicator">
          <Music size={20} />
          {chats.length > 0 && (
            <div className="collapsed-count">
              {chats.length}
            </div>
          )}
        </div>
      )}
    </div>
  )
}