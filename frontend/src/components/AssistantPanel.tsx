import React, { useEffect, useRef, useState } from 'react';
import { Sparkles, Send, X, Bot, Loader2, ShieldCheck } from 'lucide-react';
import { apiFetch } from '../lib/api';

interface Message {
  role: 'user' | 'assistant';
  text: string;
  engine?: 'llm' | 'fallback';
}

interface AskResponse {
  answer: string;
  engine: 'llm' | 'fallback';
  grounded: boolean;
  language: string;
  matched: boolean | null;
  reasons: string[];
}

const SUGGESTIONS: Record<string, string[]> = {
  en: ['Am I eligible?', 'What documents do I need?', 'How much will I get?', 'How do I apply?'],
  hi: ['क्या मैं पात्र हूँ?', 'मुझे कौन-से दस्तावेज़ चाहिए?', 'मुझे कितना मिलेगा?', 'मैं आवेदन कैसे करूँ?'],
  ta: ['நான் தகுதியானவரா?', 'என்ன ஆவணங்கள் தேவை?', 'எவ்வளவு கிடைக்கும்?', 'எப்படி விண்ணப்பிப்பது?'],
};

export const AssistantPanel: React.FC<{
  documentId: string;
  documentTitle: string;
  language: string;
}> = ({ documentId, documentTitle, language }) => {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, sending]);

  const toggle = () => {
    if (open) {
      setOpen(false);
      return;
    }
    setError(null);
    setMessages([
      {
        role: 'assistant',
        text: `Hi! I'm NoBar's verified assistant for "${documentTitle}". Ask me in your own words — I only answer from the facts verified for this scheme (eligibility, benefits, documents, steps).`,
        engine: 'llm',
      },
    ]);
    setOpen(true);
  };

  const ask = async (question: string) => {
    const q = question.trim();
    if (!q || sending) return;
    setInput('');
    setError(null);
    setMessages((m) => [...m, { role: 'user', text: q }]);
    setSending(true);
    try {
      const res = await apiFetch<AskResponse>('/api/assistant/ask', {
        method: 'POST',
        body: JSON.stringify({ document_id: documentId, question: q, language }),
      });
      setMessages((m) => [...m, { role: 'assistant', text: res.answer, engine: res.engine }]);
    } catch (err: any) {
      setError(err?.message || 'Something went wrong. Please try again.');
    } finally {
      setSending(false);
    }
  };

  return (
    <>
      {/* Floating launcher */}
      <button
        onClick={toggle}
        className="fixed bottom-6 right-6 z-40 inline-flex items-center gap-2 bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-500 hover:to-violet-500 text-white px-4 py-3 rounded-full shadow-xl font-bold text-sm transition"
        aria-label={open ? 'Close Ask NoBar assistant' : 'Open Ask NoBar assistant'}
      >
        <Sparkles className="w-4 h-4" /> {open ? 'Close' : 'Ask NoBar'}
      </button>

      {/* Drawer */}
      {open && (
        <div className="fixed inset-y-0 right-0 z-50 w-full max-w-md bg-slate-900 border-l border-slate-700 shadow-2xl flex flex-col">
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700 bg-slate-950/60">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-600 to-violet-600 flex items-center justify-center">
                <Bot className="w-4 h-4 text-white" />
              </div>
              <div>
                <p className="text-sm font-bold text-slate-100">Ask NoBar</p>
                <p className="text-[11px] text-slate-400 leading-tight">Answers grounded only in this scheme's verified facts</p>
              </div>
            </div>
            <button onClick={() => setOpen(false)} className="text-slate-400 hover:text-slate-200" aria-label="Close assistant">
              <X className="w-5 h-5" />
            </button>
          </div>

          <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-3" aria-live="polite">
            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed whitespace-pre-wrap ${
                    m.role === 'user'
                      ? 'bg-blue-600 text-white rounded-br-sm'
                      : 'bg-slate-800 text-slate-100 border border-slate-700 rounded-bl-sm'
                  }`}
                >
                  {m.text}
                  {m.role === 'assistant' && m.engine && (
                    <div className="mt-1.5 flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide">
                      {m.engine === 'llm' ? (
                        <span className="inline-flex items-center gap-1 text-violet-300">
                          <Sparkles className="w-3 h-3" /> AI answer (verified facts)
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-amber-300">
                          <ShieldCheck className="w-3 h-3" /> Grounded answer · AI offline
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {sending && (
              <div className="flex justify-start">
                <div className="bg-slate-800 border border-slate-700 rounded-2xl rounded-bl-sm px-3.5 py-2.5 text-sm text-slate-400 flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" /> Thinking with the verified facts…
                </div>
              </div>
            )}

            {error && (
              <div className="flex justify-start">
                <div className="bg-rose-950/60 border border-rose-800 rounded-2xl rounded-bl-sm px-3.5 py-2.5 text-sm text-rose-200">
                  {error}
                </div>
              </div>
            )}
          </div>

          {/* Suggestion chips */}
          <div className="px-4 pb-2 flex flex-wrap gap-2">
            {(SUGGESTIONS[language] || SUGGESTIONS.en).map((s) => (
              <button
                key={s}
                disabled={sending}
                onClick={() => ask(s)}
                className="text-xs bg-slate-800 hover:bg-slate-700 border border-slate-600 text-slate-200 rounded-full px-3 py-1 transition disabled:opacity-50"
              >
                {s}
              </button>
            ))}
          </div>

          <form
            className="px-4 pb-4 pt-1 border-t border-slate-700 flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              ask(input);
            }}
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask in any language…"
              className="flex-1 bg-slate-800 border border-slate-600 rounded-xl px-3.5 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
              aria-label="Ask NoBar a question"
            />
            <button
              type="submit"
              disabled={!input.trim() || sending}
              className="bg-blue-600 hover:bg-blue-500 text-white rounded-xl px-3.5 flex items-center justify-center transition disabled:opacity-40"
              aria-label="Send question"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      )}
    </>
  );
};