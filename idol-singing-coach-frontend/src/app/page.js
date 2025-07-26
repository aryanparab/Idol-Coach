'use client'

import { useState } from 'react'
import { useSession, signIn, signOut } from "next-auth/react"
import { LogOut, User, Music, Home } from "lucide-react"
import SongSelector from '../components/SongSelector'
import ChatInterface from '../components/ChatInterface'
import Sidebar from '../components/Sidebar'
import Link from 'next/link'
import '../styles/HomePage.css'

export default function HomePage() {
  const { data: session, status } = useSession()
  const [selectedSong, setSelectedSong] = useState(null)
  const [selectedChat, setSelectedChat] = useState(null)

  const handleSongSelected = (song) => {
    setSelectedSong(song)
    setSelectedChat(null) // Clear any selected chat when starting new song
  }

  const handleChatSelected = (chatData) => {
    setSelectedSong(chatData.song)
    setSelectedChat(chatData)
  }

  const handleNewChat = () => {
    setSelectedSong(null)
    setSelectedChat(null)
  }

  const handleChatUpdate = (updatedChat) => {
    // This callback can be used to update the sidebar with latest chat info
    // For now, we'll just log it, but you could implement real-time updates here
    console.log('Chat updated:', updatedChat)
  }

  if (status === "loading") {
    return (
      <div className="loading-screen">
        <div className="loading-content">
          <div className="spinner"></div>
          <h2>Loading your singing assistant...</h2>
        </div>
      </div>
    )
  }

  if (!session) {
    return (
      <div className="auth-screen">
        <div className="auth-card">
          <h1 className="auth-title">
            <Music size={40} />
            IDOL_COACH
          </h1>
          <p className="auth-subtitle">
            Your personal vocal coach powered by AI. Practice singing, get real-time feedback, and improve your voice.
          </p>
          <button onClick={() => signIn("google")} className="signin-button">
            <User size={20} />
            Sign in with Google
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="app-container">
      <Sidebar 
        selectedSong={selectedSong}
        onSelectChat={handleChatSelected}
        onNewChat={handleNewChat}
      />

      <div className="main-content">
        <div className="top-bar">
          <div className="nav-section">
            <Link href="/" className="home-link" onClick={handleNewChat}>
              <Home size={20} />
              <span>Home</span>
            </Link>
            {selectedSong && (
              <>
                <span className="nav-separator">/</span>
                <Link href="/" className="song-link" onClick={handleNewChat}>
                  <Music size={20} />
                  <span>Songs</span>
                </Link>
                <span className="nav-separator">/</span>
                <span className="current-song">{selectedSong}</span>
              </>
            )}
          </div>

          <div className="center-title">
            <h1 className="app-title">
              <Music size={24} color="#38a169" />
              IDOL-Coach
            </h1>
          </div>

          <div className="user-section">
            <div className="user-info">
              <div className="user-avatar">
                {session.user.image ? (
                  <img src={session.user.image} alt="User" className="user-image" />
                ) : (
                  session.user.name?.charAt(0).toUpperCase()
                )}
              </div>
              <span>Welcome, {session.user.name?.split(' ')[0]}</span>
            </div>
            <button onClick={() => signOut()} className="signout-button">
              <LogOut size={16} />
              Sign Out
            </button>
          </div>
        </div>

        <div className="content-area">
          {!selectedSong ? (
            <div className="song-selector-container">
              <div className="intro-section">
                <h2 className="intro-title">
                  <Music size={32} />
                  Welcome to Your Personal Vocal Coach
                </h2>
                <p className="intro-description">
                  Get ready to improve your singing with AI-powered feedback. 
                  Choose a song below to start your practice session, or select a previous session from the sidebar.
                </p>
              </div>
              <SongSelector onSongSelected={handleSongSelected} />
            </div>
          ) : (
            <ChatInterface 
              song={selectedSong} 
              chatData={selectedChat}
              onChatUpdate={handleChatUpdate}
            />
          )}
        </div>
      </div>
    </div>
  )
}