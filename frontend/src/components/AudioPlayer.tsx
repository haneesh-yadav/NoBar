import React, { useState, useRef } from 'react';
import { Volume2, Play, Pause, RotateCcw, MessageSquare } from 'lucide-react';

interface AudioPlayerProps {
  documentId: string;
  language: string;
  transcriptText?: string;
}

export const AudioPlayer: React.FC<AudioPlayerProps> = ({ documentId, language, transcriptText }) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [showTranscript, setShowTranscript] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const audioUrl = `/api/documents/${documentId}/audio/${language}`;

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current
        .play()
        .then(() => setIsPlaying(true))
        .catch((err) => console.warn('Audio playback error:', err));
    }
  };

  const handleRestart = () => {
    if (!audioRef.current) return;
    audioRef.current.currentTime = 0;
    audioRef.current
      .play()
      .then(() => setIsPlaying(true))
      .catch(() => {});
  };

  return (
    <div className="bg-slate-900 border border-slate-700 rounded-xl p-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-slate-200 text-sm font-semibold">
          <Volume2 className="w-5 h-5 text-blue-400" aria-hidden="true" />
          <span>Audio Narration ({language.toUpperCase()})</span>
        </div>

        <div className="flex items-center gap-2">
          {/* Native HTML5 Audio */}
          <audio
            ref={audioRef}
            src={audioUrl}
            onEnded={() => setIsPlaying(false)}
            onPause={() => setIsPlaying(false)}
            onPlay={() => setIsPlaying(true)}
            aria-label={`Audio version in ${language}`}
          />

          <button
            onClick={togglePlay}
            aria-label={isPlaying ? 'Pause audio narration' : 'Play audio narration'}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg font-medium text-xs transition shadow"
          >
            {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            {isPlaying ? 'Pause Audio' : 'Listen Now'}
          </button>

          <button
            onClick={handleRestart}
            aria-label="Restart audio from beginning"
            className="p-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg border border-slate-700"
          >
            <RotateCcw className="w-4 h-4" />
          </button>

          {transcriptText && (
            <button
              onClick={() => setShowTranscript((prev) => !prev)}
              aria-expanded={showTranscript}
              className="flex items-center gap-1.5 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium border border-slate-700"
            >
              <MessageSquare className="w-4 h-4 text-slate-400" />
              {showTranscript ? 'Hide Transcript' : 'View Transcript'}
            </button>
          )}
        </div>
      </div>

      {showTranscript && transcriptText && (
        <div className="mt-3 bg-slate-950 p-4 rounded-lg border border-slate-800 text-slate-300 text-sm max-h-48 overflow-y-auto leading-relaxed">
          <div className="text-xs font-bold text-slate-500 uppercase mb-2">Synced Narration Transcript</div>
          {transcriptText}
        </div>
      )}
    </div>
  );
};
