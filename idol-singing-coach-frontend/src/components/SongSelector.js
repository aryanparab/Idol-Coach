'use client'

import { useEffect, useState } from 'react'
import { Search, Music, Play, Loader } from 'lucide-react'
import { fetchSongs, prepareSong } from '../../lib/api'
import '../styles/SongSelector.css'

export default function SongSelector({ onSongSelected }) {
  const [songs, setSongs] = useState([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)
  const [initialLoading, setInitialLoading] = useState(true)
  const [filteredSongs, setFilteredSongs] = useState([])

  useEffect(() => {
    fetchSongs()
      .then((data) => {
        setSongs(data.songs || [])
        setFilteredSongs(data.songs || [])
        setInitialLoading(false)
      })
  }, [])

  useEffect(() => {
    if (!search.trim()) setFilteredSongs(songs)
    else setFilteredSongs(songs.filter(song => song.title.toLowerCase().includes(search.toLowerCase())))
  }, [search, songs])

  const handleSelect = async (songTitle = search) => {
    if (!songTitle.trim()) return
    setLoading(true)
    try {
      await prepareSong(songTitle)
      onSongSelected(songTitle)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="song-selector">
      <div className="selector-header">
        <h1 className="selector-title"><Music size={32} /> Choose Your Song</h1>
        <p className="selector-subtitle">Start your vocal practice session</p>
      </div>

      <div className="search-container">
        <Search className="search-icon" size={20} />
        <input
          type="text"
          className="search-input"
          placeholder="Search or enter a custom title..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>
      <button className="select-button" disabled={!search.trim() || loading} onClick={() => handleSelect()}>
        {loading ? <><Loader size={20} className="animate-spin" /> Preparing... (New Song takes up to 4 minutes)</> : <><Play size={20} /> Start</>}
      </button>

      <div className="divider"><span>or choose from available songs</span></div>

      <div className="songs-section">
        {initialLoading ? (
          <p>Loading...</p>
        ) : filteredSongs.length > 0 ? (
          <div className="songs-grid">
            {filteredSongs.map((song, idx) => (
              <div key={idx} className="song-card" onClick={() => handleSelect(song.title)}>
                <div className="song-icon"><Music size={20} /></div>
                <h3 className="song-title">{song.title}</h3>
              </div>
            ))}
          </div>
        ) : (
          <div className="empty-state">No songs match your search.</div>
        )}
      </div>
    </div>
  )
}
