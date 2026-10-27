import React, { useState, useRef, useEffect } from 'react';
import { Send, Trash2, Globe, Wrench, ExternalLink, Bot, User, Sparkles } from 'lucide-react';

export default function WebResearchTab() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState(null);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [history, loading]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed || loading) return;

    const userMessage = { role: 'user', content: trimmed };
    setHistory((prev) => [...prev, userMessage]);
    setQuery('');
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`/research?query=${encodeURIComponent(trimmed)}`);
      if (!res.ok) {
        throw new Error(`Research request failed (${res.status})`);
      }
      const data = await res.json();
      const assistantMessage = {
        role: 'assistant',
        topic: data.topic,
        summary: data.summary,
        tools_used: data.tools_used || [],
        sources: data.sources || [],
      };
      setHistory((prev) => [...prev, assistantMessage]);
    } catch (err) {
      setError(err.message || 'An error occurred during web research.');
    } finally {
      setLoading(false);
    }
  };

  const handleResetChat = async () => {
    try {
      await fetch('/research-clear-history', { method: 'POST' });
    } catch (err) {
      console.error(err);
    }
    setHistory([]);
    setError(null);
  };

  return (
    <div className="glass-card chat-card-layout">
      {/* 1. Header */}
      <div className="chat-card-header">
        <h2 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#60a5fa', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Globe size={18} /> Web Research Agent
        </h2>
        {history.length > 0 && (
          <button
            type="button"
            className="btn btn-danger-ghost"
            onClick={handleResetChat}
            title="Reset research conversation"
          >
            <Trash2 size={13} /> Reset Chat
          </button>
        )}
      </div>

      {/* 2. Scrollable Conversation Thread */}
      <div className="chat-thread-container">
        {history.length === 0 && !loading && (
          <div className="empty-state" style={{ margin: 'auto 0', padding: '40px 20px', textAlign: 'center' }}>
            <div style={{ display: 'inline-flex', padding: '12px', background: 'rgba(59, 130, 246, 0.1)', borderRadius: '50%', marginBottom: '12px' }}>
              <Globe size={32} color="#60a5fa" />
            </div>
            <h3 style={{ color: '#f4f4f5', fontSize: '1.05rem', fontWeight: 600, marginBottom: '6px' }}>
              Web Research Assistant
            </h3>
            <p style={{ color: '#a1a1aa', fontSize: '0.86rem', maxWidth: '440px', margin: '0 auto', lineHeight: '1.6' }}>
              Ask any topic below. The agent will browse the live web, read pages, extract sources, and synthesize an executive briefing.
            </p>
          </div>
        )}

        {history.map((msg, idx) => (
          <div
            key={idx}
            className={`chat-turn ${msg.role === 'user' ? 'chat-turn-user' : 'chat-turn-assistant'}`}
          >
            {msg.role === 'user' ? (
              <>
                <span className="chat-header-role user-role">
                  <User size={13} /> You
                </span>
                <div className="user-bubble">{msg.content}</div>
              </>
            ) : (
              <>
                <span className="chat-header-role">
                  <Bot size={13} /> Research Agent
                </span>
                <div className="assistant-bubble">
                  {msg.topic && (
                    <h3 style={{ fontSize: '1.05rem', color: '#60a5fa', fontWeight: 700, marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <Sparkles size={16} /> {msg.topic}
                    </h3>
                  )}
                  <div className="answer-body">{msg.summary}</div>

                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px', borderTop: '1px solid rgba(255,255,255,0.06)', marginTop: '14px', paddingTop: '10px', fontSize: '0.8rem', color: '#a1a1aa' }}>
                    {msg.tools_used && msg.tools_used.length > 0 && (
                      <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                        <Wrench size={12} color="#60a5fa" />
                        <strong>Tools:</strong> {Array.isArray(msg.tools_used) ? msg.tools_used.join(', ') : msg.tools_used}
                      </span>
                    )}
                    {msg.sources && msg.sources.length > 0 && (
                      <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                        <ExternalLink size={12} color="#60a5fa" />
                        <strong>Sources:</strong> {Array.isArray(msg.sources) ? msg.sources.join(', ') : msg.sources}
                      </span>
                    )}
                  </div>
                </div>
              </>
            )}
          </div>
        ))}

        {loading && (
          <div className="chat-turn chat-turn-assistant">
            <span className="chat-header-role">
              <Bot size={13} /> Research Agent
            </span>
            <div className="assistant-bubble" style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#a1a1aa', fontSize: '0.88rem' }}>
              <span className="spinner" />
              <span>Analyzing live web sources and compiling research synthesis...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* 3. Error Alert (if any) */}
      {error && (
        <div style={{ marginBottom: '10px', padding: '10px 14px', background: 'rgba(239, 68, 68, 0.15)', border: '1px solid #ef4444', color: '#fca5a5', borderRadius: '8px', fontSize: '0.85rem' }}>
          {error}
        </div>
      )}

      {/* 4. Bottom Input Form (Chatbot style) */}
      <div className="chat-input-wrapper">
        <form onSubmit={handleSubmit} className="search-bar">
          <input
            type="text"
            className="search-input"
            placeholder="Ask a research question (e.g. Latest breakthroughs in solid state batteries)..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={loading}
            autoFocus
          />
          <button type="submit" className="btn btn-primary" disabled={loading || !query.trim()}>
            {loading ? (
              <>
                <span className="spinner" /> Researching...
              </>
            ) : (
              <>
                <Send size={15} /> Research
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
