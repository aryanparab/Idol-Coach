import { getSongDetails } from '../../lib/api';
import { Music, Volume2, FileText, Play, Pause, SkipBack, SkipForward, X ,VolumeX} from 'lucide-react';
import { useEffect, useState, useRef } from 'react';

export default function ChatHeader({ song }) {
  const [songData, setSongData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState(null);
  const [isPlaying1, setIsPlaying1] = useState(false);
  const [isPlaying2, setIsPlaying2] = useState(false);
  const [audioError1, setAudioError1] = useState(null);
  const [audioError2, setAudioError2] = useState(null);
  

  //karaoke states 
  const [isKaraokeePlaying,setIsKaraokeePlaying] = useState(false);
  const [karaokeCurrentTime,setKaraokeCurrentTime] = useState(0);
  const [karaokeDuration,setKaraokeDuration] = useState(0);
  const [karaokeVolume,setKaraokeVolume] = useState(1);
  const [karaokeIsMuted,setKaraokeIsMuted] = useState(false);
  const [currentWordIndex,setCurrentWordIndex] = useState(-1);
  const [karaokeAudioType,setKaraokeAudioType]= useState('vocals');
  const [processedLyrics, setProcessedLyrics] = useState([]);

  const audio1Ref = useRef(null);
  const audio2Ref = useRef(null);
  const karaokeAudioRef = useRef(null);
  const lyricsContainerRef = useRef(null);
  
  useEffect(() => {
    if (song) {
      fetchSongData(song);
    }
  }, [song]);

  useEffect(() => {
  if (songData?.audio_urls?.length > 0) {
    console.log('Testing audio URLs...');
    songData.audio_urls.forEach((url, index) => {
      const processedUrl = getAudioUrl(url);
      console.log(`Audio ${index + 1} URL:`, processedUrl);
      
      // Test if URL is accessible
      fetch(processedUrl, { method: 'HEAD', mode: 'no-cors' })
        .then(() => console.log(`✅ Audio ${index + 1} URL is accessible`))
        .catch(err => console.error(`❌ Audio ${index + 1} URL error:`, err));
    });
  }
}, [songData]);

// Process lyrics when song data changes
useEffect(() => {
  if (songData?.timestamp_lyrics) {
    const processed = processTimestampLyrics(songData.timestamp_lyrics);
    setProcessedLyrics(processed);
    console.log('Processed lyrics for karaoke:', processed);
  }
}, [songData]);

// Enhanced karaoke timing effect
useEffect(() => {
  if (activeTab === 'karaoke' && isKaraokeePlaying && processedLyrics.length > 0) {
    const updateTime = () => {
      if (karaokeAudioRef.current) {
        const currentTime = karaokeAudioRef.current.currentTime;
        setKaraokeCurrentTime(currentTime);

        // Find the current word based on timestamp
        let newWordIndex = -1;
        
        for (let i = 0; i < processedLyrics.length; i++) {
          const word = processedLyrics[i];
          const wordStart = word.start || word.startTime || word.time || 0;
          const nextWord = processedLyrics[i + 1];
          const wordEnd = nextWord ? (nextWord.start || nextWord.startTime || nextWord.time) : karaokeDuration;
          
          // Check if current time is within this word's time range
          if (currentTime >= wordStart && currentTime < wordEnd) {
            newWordIndex = i;
            break;
          }
        }

        // Update current word index if it changed
        if (newWordIndex !== currentWordIndex) {
          setCurrentWordIndex(newWordIndex);
          if (newWordIndex !== -1) {
            scrollToCurrentWord(newWordIndex);
          }
        }
      }
    };

    // Update more frequently for smoother highlighting
    const interval = setInterval(updateTime, 50);
    return () => clearInterval(interval);
  }
}, [activeTab, isKaraokeePlaying, currentWordIndex, processedLyrics, karaokeDuration]);

  // Enhanced function to process timestamp lyrics
  const processTimestampLyrics = (data) => {
    console.log('=== PROCESSING TIMESTAMP LYRICS ===');
    console.log('Raw data:', data);
    console.log('Type:', typeof data);
    console.log('Is array:', Array.isArray(data));
    
    let lyricsArray = [];
    
    if (Array.isArray(data)) {
      lyricsArray = data;
    } else if (typeof data === 'object' && data !== null) {
      // Try different common properties
      if (data.words && Array.isArray(data.words)) {
        lyricsArray = data.words;
      } else if (data.lyrics && Array.isArray(data.lyrics)) {
        lyricsArray = data.lyrics;
      } else if (data.data && Array.isArray(data.data)) {
        lyricsArray = data.data;
      } else {
        // Convert object to array if it has numeric keys
        const keys = Object.keys(data);
        if (keys.length > 0 && keys.every(k => !isNaN(k))) {
          lyricsArray = Object.values(data);
        }
      }
    } else if (typeof data === 'string') {
      try {
        const parsed = JSON.parse(data);
        return processTimestampLyrics(parsed); // Recursive call
      } catch (e) {
        console.error('Failed to parse JSON string:', e);
      }
    }
    
    // Validate and normalize the lyrics array
    const validLyrics = lyricsArray.filter(item => {
      if (!item || typeof item !== 'object') return false;
      
      // Must have a word/text and a timestamp
      const hasText = item.word || item.text;
      const hasTime = typeof (item.start || item.startTime || item.time) === 'number';
      
      return hasText && hasTime;
    }).map(item => ({
      word: item.word || item.text || '',
      start: item.start || item.startTime || item.time || 0,
      end: item.end || item.endTime || null
    }));
    
    // Sort by start time to ensure proper order
    validLyrics.sort((a, b) => a.start - b.start);
    
    console.log('Processed lyrics count:', validLyrics.length);
    console.log('First few processed items:', validLyrics.slice(0, 3));
    console.log('=====================================');
    
    return validLyrics;
  };

  const fetchSongData = async (song) => {
    setLoading(true);
    try {
      const resp = await getSongDetails(song);
      if (resp.ok) {
        const data = await resp.json();
        console.log('Fetched song data:', data);
        setSongData(data);
      }
    } catch (error) {
      console.error('Error fetching song data:', error);
    }
    setLoading(false);
  };

  const toggleTab = (tabName) => {
    if (activeTab !== tabName) {
      // Stop all audio when switching tabs
      if (audio1Ref.current && !audio1Ref.current.paused) {
        audio1Ref.current.pause();
        setIsPlaying1(false);
      }
      if (audio2Ref.current && !audio2Ref.current.paused) {
        audio2Ref.current.pause();
        setIsPlaying2(false);
      }
      if (karaokeAudioRef.current && !karaokeAudioRef.current.paused) {
        karaokeAudioRef.current.pause();
        setIsKaraokeePlaying(false);
      }
      // Reset karaoke state when switching away
      setCurrentWordIndex(-1);
      setKaraokeCurrentTime(0);
    }
    setActiveTab(activeTab === tabName ? null : tabName);
  };

  const getAudioUrl = (audioUrl) => {
  if (!audioUrl) return null;

  console.log('Original audio URL:', audioUrl);

  // Already a valid URL (http, https, or presigned)
  if (audioUrl.startsWith('http://') || audioUrl.startsWith('https://')) {
    console.log('Using direct URL:', audioUrl);
    return audioUrl;
  }

  // Handle s3:// links by converting to HTTPS
  if (audioUrl.startsWith('s3://')) {
    const match = audioUrl.match(/^s3:\/\/([^\/]+)\/(.+)$/);
    if (!match) return null;
    const bucket = match[1];
    const key = match[2];
    const convertedUrl = `https://${bucket}.s3.amazonaws.com/${encodeURIComponent(key)}`;
    console.log('Converted S3 URL:', convertedUrl);
    return convertedUrl;
  }

  // Fallback for local path
  const songPath = audioUrl.startsWith('songs/') ? audioUrl.slice(6) : audioUrl;
  const fallbackUrl = `/coach/songs/${songPath}`;
  console.log('Using fallback URL:', fallbackUrl);
  return fallbackUrl;
};

// Fixed and improved scrollToCurrentWord function
const scrollToCurrentWord = (wordIndex) => {
  const container = lyricsContainerRef.current;
  const wordElement = container?.querySelector(`[data-word-index="${wordIndex}"]`);
  if (wordElement && container) {
    const containerRect = container.getBoundingClientRect();
    const wordRect = wordElement.getBoundingClientRect();

    // Check if word is outside the visible area
    const isOutOfView = wordRect.top < containerRect.top + 50 || 
                       wordRect.bottom > containerRect.bottom - 50;

    if (isOutOfView) {
      wordElement.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
        inline: 'nearest'
      });
    }
  }
};

const toggleKaraokePlay = () => {
  if (karaokeAudioRef.current) {
    if (isKaraokeePlaying) {
      karaokeAudioRef.current.pause();
    } else {
      const playPromise = karaokeAudioRef.current.play();
      if (playPromise !== undefined) {
        playPromise.catch(error => {
          console.error('Karaoke playback error:', error);
        });
      }
    }
    setIsKaraokeePlaying(!isKaraokeePlaying);
  }
};

const handleWordClick = (word, index) => {
  if (karaokeAudioRef.current && word.start !== undefined) {
    const startTime = word.start;
    karaokeAudioRef.current.currentTime = startTime;
    setKaraokeCurrentTime(startTime);
    setCurrentWordIndex(index);
    
    // Resume playing if it was paused
    if (!isKaraokeePlaying) {
      toggleKaraokePlay();
    }
  }
};

const handleKaraokeTimelineClick = (e) => {
  if (karaokeAudioRef.current && karaokeDuration > 0) {
    const rect = e.currentTarget.getBoundingClientRect();
    const percent = (e.clientX - rect.left) / rect.width;
    const newTime = percent * karaokeDuration;
    karaokeAudioRef.current.currentTime = newTime;
    setKaraokeCurrentTime(newTime);
  }
};

const handleKaraokeVolumeChange = (e) => {
  const newVolume = parseFloat(e.target.value);
  setKaraokeVolume(newVolume);
  if (karaokeAudioRef.current) {
    karaokeAudioRef.current.volume = newVolume;
  }
};

const toggleKaraokeMute = () => {
  if (karaokeAudioRef.current) {
    karaokeAudioRef.current.muted = !karaokeIsMuted;
    setKaraokeIsMuted(!karaokeIsMuted);
  }
}

const skipKaraokeTime = (seconds) => {
  if (karaokeAudioRef.current) {
    const newTime = Math.max(0, Math.min(karaokeDuration, karaokeCurrentTime + seconds));
    karaokeAudioRef.current.currentTime = newTime;
    setKaraokeCurrentTime(newTime);
  }
};

const formatTime = (time) => {
  const minutes = Math.floor(time / 60);
  const seconds = Math.floor(time % 60);
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

  const togglePlay = (audioNumber) => {
  const audioRef = audioNumber === 1 ? audio1Ref : audio2Ref;
  const setIsPlaying = audioNumber === 1 ? setIsPlaying1 : setIsPlaying2;
  const otherAudioRef = audioNumber === 1 ? audio2Ref : audio1Ref;
  const setOtherIsPlaying = audioNumber === 1 ? setIsPlaying2 : setIsPlaying1;

  if (audioRef.current) {
    const audioSrc = audioRef.current.src;
    console.log(`Audio ${audioNumber} source:`, audioSrc);
    console.log(`Audio ${audioNumber} readyState:`, audioRef.current.readyState);
    console.log(`Audio ${audioNumber} networkState:`, audioRef.current.networkState);
    
    if (!audioSrc || audioSrc === window.location.href) {
      console.error('Invalid audio source:', audioSrc);
      return;
    }

    if (audioRef.current.paused) {
      // Stop other audio if playing
      if (otherAudioRef.current && !otherAudioRef.current.paused) {
        otherAudioRef.current.pause();
        setOtherIsPlaying(false);
      }

      // Try to load the audio first
      audioRef.current.load();
      
      const playPromise = audioRef.current.play();
      if (playPromise !== undefined) {
        playPromise
          .then(() => {
            console.log(`Audio ${audioNumber} started playing successfully`);
            setIsPlaying(true);
          })
          .catch((error) => {
            console.error(`Error playing audio ${audioNumber}:`, error);
            console.error('Error name:', error.name);
            console.error('Error message:', error.message);
            setIsPlaying(false);
          });
      }
    } else {
      audioRef.current.pause();
      setIsPlaying(false);
    }
  }
};

  const skipTime = (audioNumber, seconds) => {
    const audioRef = audioNumber === 1 ? audio1Ref : audio2Ref;
    if (audioRef.current) {
      audioRef.current.currentTime += seconds;
    }
  };

  const handleAudioEnd = (audioNumber) => {
    const setIsPlaying = audioNumber === 1 ? setIsPlaying1 : setIsPlaying2;
    setIsPlaying(false);
  };

  const handleAudioError = (audioNumber, e) => {
  const setAudioError = audioNumber === 1 ? setAudioError1 : setAudioError2;
  const setIsPlaying = audioNumber === 1 ? setIsPlaying1 : setIsPlaying2;

  const mediaError = e?.target?.error;
  const audioSrc = e?.target?.src;
  
  console.error(`=== Audio ${audioNumber} Error Debug Info ===`);
  console.error('Audio source:', audioSrc);
  console.error('Error object:', mediaError);
  console.error('Event:', e);
  console.error('ReadyState:', e?.target?.readyState);
  console.error('NetworkState:', e?.target?.networkState);
  
  let errorMessage = 'Unknown audio error';

  if (mediaError) {
    console.error('Media error code:', mediaError.code);
    console.error('Media error message:', mediaError.message);
    
    switch (mediaError.code) {
      case mediaError.MEDIA_ERR_ABORTED:
        errorMessage = 'Audio playback was aborted.';
        break;
      case mediaError.MEDIA_ERR_NETWORK:
        errorMessage = 'Network error loading audio. Check CORS configuration.';
        break;
      case mediaError.MEDIA_ERR_DECODE:
        errorMessage = 'Audio decoding error. File may be corrupted or unsupported format.';
        break;
      case mediaError.MEDIA_ERR_SRC_NOT_SUPPORTED:
        errorMessage = 'Audio format not supported or URL is incorrect. Check CORS and file format.';
        break;
      default:
        errorMessage = `Unknown media error (code: ${mediaError.code}).`;
        break;
    }
  }

  console.error(`Audio ${audioNumber} playback error:`, errorMessage);
  setAudioError(errorMessage);
  setIsPlaying(false);
};

const handleAudioCanPlay = (audioNumber) => {
  const setAudioError = audioNumber === 1 ? setAudioError1 : setAudioError2;
  console.log(`Audio ${audioNumber} can play - clearing errors`);
  setAudioError(null);
};

  return (
    <div className="chat-header">
      <div className="header-main">
        <h2><Music size={24} /> IDOL-COACH</h2>
        <p><Volume2 size={18} /> Practicing: {song}</p>

        {songData && (
          <div className="action-icons">
            <>
           { songData.timestamp_lyrics &&
           ( <button onClick={() => toggleTab('karaoke')} className={`icon-button ${activeTab === 'karaoke' ? 'active' : ''}`}>
                  <Music size={24} /><span className="audio-label">karaoke</span>
                </button>
              )}
            </>
            {songData.audio_urls && songData.audio_urls.length > 0 && (
              <>
                <button onClick={() => toggleTab('audio1')} className={`icon-button ${activeTab === 'audio1' ? 'active' : ''}`}>
                  <Music size={24} /><span className="audio-label">1</span>
                </button>
                {songData.audio_urls.length > 1 && (
                  <button onClick={() => toggleTab('audio2')} className={`icon-button ${activeTab === 'audio2' ? 'active' : ''}`}>
                    <Music size={24} /><span className="audio-label">2</span>
                  </button>
                )}
              </>
            )}

            {songData.lyrics && (
              <button onClick={() => toggleTab('lyrics')} className={`icon-button ${activeTab === 'lyrics' ? 'active' : ''}`}>
                <FileText size={24} />
              </button>
            )}
          </div>
        )}
      </div>

      {activeTab && (
        <div className="tab-container">
          <div className="tab-header">
            <h3>{activeTab === 'lyrics' ? 'Lyrics' : activeTab==='karaoke' ? 'Karaoke' : `Audio Track ${activeTab === 'audio1' ? 1 : 2}`}</h3>
            <button onClick={() => setActiveTab(null)} className="close-button"><X size={20} /></button>
          </div>

          <div className="tab-content">
            {activeTab==='karaoke' && songData?.timestamp_lyrics && (
              <div className ="Karaoke-container" style= {{
                maxHeight: '500px', 
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                borderRadius: '12px',
                padding: '20px',
                color: 'white'
              }}>
                <div style={{ marginBottom: '15px' }}>
                  <label style={{ marginRight: '10px' }}>Audio Track:</label>
                  <select 
                    value={karaokeAudioType} 
                    onChange={(e) => setKaraokeAudioType(e.target.value)}
                    style={{ 
                      padding: '5px 10px', 
                      borderRadius: '5px', 
                      border: 'none',
                      backgroundColor: 'rgba(255,255,255,0.2)',
                      color: 'white'
                    }}
                  >
                    <option value="vocals">Vocals</option>
                    <option value="accompaniment">Accompaniment</option>
                  </select>
                </div>
                <audio 
                  ref={karaokeAudioRef}
                  src={getAudioUrl(songData.audio_urls?.[karaokeAudioType==='accompaniment' ? 1 :0])}
                  onLoadedMetadata={() => {
                    if (karaokeAudioRef.current) {
                      setKaraokeDuration(karaokeAudioRef.current.duration || 0);
                    }
                  }}
                  onTimeUpdate={() => {
                    if (karaokeAudioRef.current) {
                      setKaraokeCurrentTime(karaokeAudioRef.current.currentTime || 0);
                    }
                  }}
                  onEnded={() => {
                    setIsKaraokeePlaying(false);
                    setCurrentWordIndex(-1);
                  }}
                  onPause={() => setIsKaraokeePlaying(false)}
                  onPlay={() => setIsKaraokeePlaying(true)}
                  preload="metadata" 
                />

                  <div 
                  onClick={handleKaraokeTimelineClick}
                  style={{
                    width: '100%',
                    height: '6px',
                    backgroundColor: 'rgba(255,255,255,0.3)',
                    borderRadius: '3px',
                    cursor: 'pointer',
                    marginBottom: '15px',
                    position: 'relative'
                  }}
                >
                  <div style={{
                    width: `${karaokeDuration > 0 ? (karaokeCurrentTime / karaokeDuration) * 100 : 0}%`,
                    height: '100%',
                    backgroundColor: '#4ade80',
                    borderRadius: '3px',
                    transition: 'width 0.1s ease'
                  }} />
                </div>

                <div style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'center', 
                  gap: '15px',
                  marginBottom: '20px'
                }}>
                  <button 
                    onClick={() => skipKaraokeTime(-10)}
                    style={{ 
                      background: 'rgba(255,255,255,0.2)', 
                      border: 'none', 
                      borderRadius: '50%', 
                      padding: '10px',
                      color: 'white',
                      cursor: 'pointer'
                    }}
                  >
                    <SkipBack size={20} />
                  </button>
                  
                  <button 
                    onClick={toggleKaraokePlay}
                    style={{ 
                      background: '#4ade80', 
                      border: 'none', 
                      borderRadius: '50%', 
                      padding: '15px',
                      color: 'white',
                      cursor: 'pointer'
                    }}
                  >
                    {isKaraokeePlaying ? <Pause size={24} /> : <Play size={24} />}
                  </button>
                  
                  <button 
                    onClick={() => skipKaraokeTime(10)}
                    style={{ 
                      background: 'rgba(255,255,255,0.2)', 
                      border: 'none', 
                      borderRadius: '50%', 
                      padding: '10px',
                      color: 'white',
                      cursor: 'pointer'
                    }}
                  >
                    <SkipForward size={20} />
                  </button>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginLeft: '20px' }}>
                    <button 
                      onClick={toggleKaraokeMute}
                      style={{ 
                        background: 'none', 
                        border: 'none', 
                        color: 'white',
                        cursor: 'pointer'
                      }}
                    >
                      {karaokeIsMuted ? <VolumeX size={20} /> : <Volume2 size={20} />}
                    </button>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.1"
                      value={karaokeIsMuted ? 0 : karaokeVolume}
                      onChange={handleKaraokeVolumeChange}
                      style={{ width: '80px' }}
                    />
                  </div>

                  <div style={{ marginLeft: '20px', fontSize: '14px' }}>
                    {formatTime(karaokeCurrentTime)} / {formatTime(karaokeDuration)}
                  </div>
                </div>
                  
              <div 
                ref={lyricsContainerRef}
                style={{
                  maxHeight: '300px',
                  overflowY: 'auto',
                  padding: '20px',
                  backgroundColor: 'rgba(0,0,0,0.3)',
                  borderRadius: '8px',
                  lineHeight: '2.5',
                  fontSize: '18px',
                  textAlign: 'center'
                }}
              >
                {/* Enhanced karaoke lyrics rendering */}
                {processedLyrics.length > 0 ? (
                  <div style={{ lineHeight: '2.5', fontSize: '18px' }}>
                    {processedLyrics.map((word, index) => {
                      const isActive = index === currentWordIndex;
                      const isPast = index < currentWordIndex;
                      
                      return (
                        <span
                          key={index}
                          data-word-index={index}
                          onClick={() => handleWordClick(word, index)}
                          style={{
                            margin: '0 8px 15px 8px',
                            padding: '4px 8px',
                            borderRadius: '4px',
                            cursor: 'pointer',
                            backgroundColor: isActive ? '#4ade80' : isPast ? 'rgba(74, 222, 128, 0.3)' : 'transparent',
                            color: isActive ? 'black' : 'white',
                            fontWeight: isActive ? 'bold' : 'normal',
                            transform: isActive ? 'scale(1.1)' : 'scale(1)',
                            transition: 'all 0.3s ease',
                            display: 'inline-block',
                            border: isActive ? '2px solid #22c55e' : '1px solid transparent',
                            textShadow: isActive ? 'none' : '1px 1px 2px rgba(0,0,0,0.5)'
                          }}
                          title={`${word.word} (${formatTime(word.start)})`}
                        >
                          {word.word}{' '}
                        </span>
                      );
                    })}
                  </div>
                ) : (
                  <div style={{ color: 'white', textAlign: 'center', padding: '20px' }}>
                    <p>Processing timestamp lyrics...</p>
                    <p style={{ fontSize: '14px', opacity: 0.7 }}>
                      {songData?.timestamp_lyrics ? 'Data found, but unable to process format' : 'No timestamp data available'}
                    </p>
                    {songData?.timestamp_lyrics && (
                      <details style={{ marginTop: '10px', fontSize: '12px', opacity: 0.5 }}>
                        <summary>Debug Info</summary>
                        <pre style={{ textAlign: 'left', overflow: 'auto', maxHeight: '100px' }}>
                          {JSON.stringify(songData.timestamp_lyrics, null, 2).substring(0, 500)}...
                        </pre>
                      </details>
                    )}
                  </div>
                )}
              </div>
              </div>
            )}
   
            {activeTab === 'lyrics' && songData?.lyrics && (
              <div className="lyrics-display">
                <pre>{songData.lyrics}</pre>
              </div>
            )}

            {['audio1', 'audio2'].includes(activeTab) && songData?.audio_urls?.length > 0 && (
              <div className="audio-player">
                <p>{songData.audio_files?.[activeTab === 'audio1' ? 0 : 1] || 'Audio File'}</p>
                <audio
  ref={activeTab === 'audio1' ? audio1Ref : audio2Ref}
  src={getAudioUrl(songData.audio_urls[activeTab === 'audio1' ? 0 : 1])}
  onEnded={() => handleAudioEnd(activeTab === 'audio1' ? 1 : 2)}
  onCanPlay={() => handleAudioCanPlay(activeTab === 'audio1' ? 1 : 2)}
  onError={(e) => handleAudioError(activeTab === 'audio1' ? 1 : 2, e)}
  onLoadStart={() => console.log(`Audio ${activeTab === 'audio1' ? 1 : 2} load started`)}
  onLoadedData={() => console.log(`Audio ${activeTab === 'audio1' ? 1 : 2} data loaded`)}
  onLoadedMetadata={() => console.log(`Audio ${activeTab === 'audio1' ? 1 : 2} metadata loaded`)}
  preload="metadata"
/>
                <div className="audio-controls">
                  <button onClick={() => skipTime(activeTab === 'audio1' ? 1 : 2, -10)}><SkipBack /></button>
                  <button onClick={() => togglePlay(activeTab === 'audio1' ? 1 : 2)}>
                    {activeTab === 'audio1' ? (isPlaying1 ? <Pause /> : <Play />) : (isPlaying2 ? <Pause /> : <Play />)}
                  </button>
                  <button onClick={() => skipTime(activeTab === 'audio1' ? 1 : 2, 10)}><SkipForward /></button>
                </div>
                {(activeTab === 'audio1' && audioError1) || (activeTab === 'audio2' && audioError2) ? (
                  <p className="audio-error">{activeTab === 'audio1' ? audioError1 : audioError2}</p>
                ) : null}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}