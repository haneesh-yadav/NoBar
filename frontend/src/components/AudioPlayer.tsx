import React, { useEffect, useRef, useState } from 'react';
import { Volume2, Play, Pause, StopCircle, Radio, MessageSquare } from 'lucide-react';

interface AudioPlayerProps {
  documentId: string;
  language: string;
  transcriptText?: string;
  hasRecording?: boolean;
}

const LOCALES: Record<string, string> = { en: 'en-IN', hi: 'hi-IN', ta: 'ta-IN' };
const LANG_NAMES: Record<string, string> = { en: 'English (India)', hi: 'हिन्दी', ta: 'தமிழ்' };

function browserSpeechAvailable(): boolean {
  return typeof window !== 'undefined' && 'speechSynthesis' in window && typeof SpeechSynthesisUtterance !== 'undefined';
}

function pickVoice(lang: string, voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | undefined {
  const prefix = lang.slice(0, 2).toLowerCase();
  return (
    voices.find((v) => v.lang.toLowerCase().startsWith(lang.toLowerCase())) ||
    voices.find((v) => v.lang.toLowerCase().startsWith(prefix)) ||
    voices.find((v) => v.lang.toLowerCase().startsWith('en'))
  );
}

export const AudioPlayer: React.FC<AudioPlayerProps> = ({
  documentId,
  language,
  transcriptText,
  hasRecording,
}) => {
  const [showTranscript, setShowTranscript] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [paused, setPaused] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const speechSupported = browserSpeechAvailable();

  const locale = LOCALES[language] || 'en-IN';
  const audioUrl = `/api/documents/${documentId}/audio/${language}`;

  // Always stop any running speech when the document/language changes or on unmount.
  useEffect(() => {
    if (speechSupported) window.speechSynthesis.cancel();
    setSpeaking(false);
    setPaused(false);
    setStatus(null);
  }, [documentId, language, speechSupported]);

  useEffect(() => () => {
    if (speechSupported) window.speechSynthesis.cancel();
  }, [speechSupported]);

  const handleStop = () => {
    if (speechSupported) window.speechSynthesis.cancel();
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    setSpeaking(false);
    setPaused(false);
    setStatus(null);
  };

  const startBrowserSpeech = () => {
    if (!speechSupported || !transcriptText) return false;
    const synth = window.speechSynthesis;
    synth.cancel();
    const utterance = new SpeechSynthesisUtterance(transcriptText);
    utterance.lang = locale;
    utterance.rate = 0.95;
    const voices = synth.getVoices();
    const voice = pickVoice(locale, voices);
    if (voice) utterance.voice = voice;
    utterance.onstart = () => {
      setSpeaking(true);
      setPaused(false);
    };
    utterance.onend = () => {
      setSpeaking(false);
      setPaused(false);
    };
    utterance.onerror = (event) => {
      setSpeaking(false);
      setStatus(event.error === 'interrupted' ? null : `Browser voice could not read this language (${LANG_NAMES[language] || language}).`);
    };
    synth.speak(utterance);
    return true;
  };

  const handleListen = () => {
    setStatus(null);
    // Preferred: the browser's own screen-reader voice — works for every
    // document (translations included) with zero server audio to generate.
    if (transcriptText && speechSupported) {
      if (speaking && !paused) {
        window.speechSynthesis.pause();
        setPaused(true);
        return;
      }
      if (paused) {
        window.speechSynthesis.resume();
        setPaused(false);
        return;
      }
      startBrowserSpeech();
      return;
    }
    // Fallback: the pipeline-generated native recording (if any).
    if (audioRef.current) {
      audioRef.current
        .play()
        .then(() => setStatus(null))
        .catch((err) => {
          console.warn('Server audio unavailable:', err);
          setStatus('No narration is available for this document yet.');
        });
    }
  };

  const hasAnyAudio = hasRecording || speechSupported;

  return (
    <div className="bg-slate-900 border border-slate-700 rounded-xl p-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-slate-200 text-sm font-semibold">
          <Volume2 className="w-5 h-5 text-blue-400" aria-hidden="true" />
          <span>Listen — Read Aloud ({LANG_NAMES[language] || language.toUpperCase()})</span>
          {hasRecording && (
            <span className="inline-flex items-center gap-1 text-[10px] font-bold bg-emerald-950 text-emerald-300 border border-emerald-800 px-2 py-0.5 rounded">
              <Radio className="w-3 h-3" /> Studio Recording
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {hasRecording && (
            <audio
              ref={audioRef}
              src={audioUrl}
              onEnded={handleStop}
              onPause={() => setSpeaking(false)}
              onPlay={() => setSpeaking(true)}
              aria-label={`Audio version in ${language}`}
            />
          )}

          {hasAnyAudio ? (
            <>
              <button
                onClick={handleListen}
                aria-label={speaking && !paused ? 'Pause narration' : 'Listen to the scheme in speech'}
                className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg font-medium text-xs transition shadow"
              >
                {speaking && !paused ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                {speaking && !paused ? 'Pause' : paused ? 'Resume' : 'Listen Now'}
              </button>

              <button
                onClick={handleStop}
                disabled={!speaking && !paused}
                aria-label="Stop narration"
                className={`p-2 rounded-lg border transition ${
                  speaking || paused
                    ? 'bg-slate-800 hover:bg-slate-700 text-slate-300 border-slate-600'
                    : 'bg-slate-900 text-slate-600 border-slate-800 cursor-not-allowed'
                }`}
              >
                <StopCircle className="w-4 h-4" />
              </button>
            </>
          ) : (
            <span className="text-xs text-slate-500">
              Narration isn't available for this document yet.
            </span>
          )}

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

      {status && (
        <p className="text-xs text-amber-300">{status}</p>
      )}

      {!speechSupported && !hasRecording && (
        <p className="text-[11px] text-slate-500">
          Your browser doesn't support text-to-speech and no recording was generated for this
          document — try a Chromium browser for read-aloud.
        </p>
      )}

      {showTranscript && transcriptText && (
        <div className="mt-3 bg-slate-950 p-4 rounded-lg border border-slate-800 text-slate-300 text-sm max-h-48 overflow-y-auto leading-relaxed">
          <div className="text-xs font-bold text-slate-500 uppercase mb-2">
            Narration Transcript — {LANG_NAMES[language] || language.toUpperCase()}
          </div>
          {transcriptText}
        </div>
      )}
    </div>
  );
};