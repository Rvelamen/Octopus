import React, { useState, useEffect, useRef } from 'react';
import { Volume2, Play, Pause, X } from 'lucide-react';
import './TTSPlayer.css';

function TTSPlayer({ audioData, format, text, durationMs, onClose }) {
  const audioRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  useEffect(() => {
    if (audioRef.current && audioData) {
      audioRef.current.src = `data:audio/${format};base64,${audioData}`;
      audioRef.current.load();
    }
  }, [audioData, format]);

  const handlePlayPause = async () => {
    if (!audioRef.current) return;
    
    try {
      if (isPlaying) {
        audioRef.current.pause();
      } else {
        await audioRef.current.play();
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        console.warn('Audio play error:', err);
      }
      setIsPlaying(false);
    }
  };

  const handleTimeUpdate = () => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime);
    }
  };

  const handleLoadedMetadata = () => {
    if (audioRef.current) {
      setDuration(audioRef.current.duration);
    }
  };

  const handleEnded = () => {
    setIsPlaying(false);
    setCurrentTime(0);
  };

  const handlePlay = () => setIsPlaying(true);
  const handlePause = () => setIsPlaying(false);

  const formatTime = (time) => {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  const handleSeek = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const percentage = x / rect.width;
    if (audioRef.current) {
      audioRef.current.currentTime = percentage * duration;
    }
  };

  return (
    <div className="tts-message-player">
      <audio
        ref={audioRef}
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        onEnded={handleEnded}
        onPlay={handlePlay}
        onPause={handlePause}
      />
      
      <div className="tts-player-inline">
        <div className="tts-player-icon">
          <Volume2 size={14} />
        </div>
        
        <button className="tts-player-btn-small" onClick={handlePlayPause}>
          {isPlaying ? <Pause size={12} /> : <Play size={12} />}
        </button>
        
        <div className="tts-player-progress" onClick={handleSeek}>
          <div 
            className="tts-player-progress-bar" 
            style={{ width: `${duration > 0 ? (currentTime / duration) * 100 : 0}%` }}
          />
        </div>
        
        <div className="tts-player-time-small">
          {formatTime(currentTime)} / {formatTime(duration)}
        </div>
        
        {text && (
          <div className="tts-player-text-small" title={text}>
            {text.length > 20 ? text.substring(0, 20) + '...' : text}
          </div>
        )}
        
        <button className="tts-player-close-small" onClick={onClose}>
          <X size={12} />
        </button>
      </div>
    </div>
  );
}

export default TTSPlayer;
