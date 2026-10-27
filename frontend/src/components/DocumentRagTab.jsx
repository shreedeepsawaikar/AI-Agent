import React, { useState, useEffect, useRef } from 'react';
import { FileText, Upload, RefreshCw, Trash2, Send, Bot, User, CheckCircle2, ChevronDown, ChevronRight, MessageSquare } from 'lucide-react';

export default function DocumentRagTab() {
  const [files, setFiles] = useState([]);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [reindexing, setReindexing] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [statusMsg, setStatusMsg] = useState(null);

  const [query, setQuery] = useState('');
  const [querying, setQuerying] = useState(false);
  const [history, setHistory] = useState([]);
  const [queryError, setQueryError] = useState(null);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [history, querying]);

  // Fetch current context files on mount
  const loadFiles = async () => {
    setLoadingFiles(true);
    try {
      const res = await fetch('/rag-files');
      if (res.ok) {
        const data = await res.json();
        setFiles(data.files || []);
      }
    } catch (err) {
      console.error('Failed to load context files', err);
    } finally {
      setLoadingFiles(false);
    }
  };

  useEffect(() => {
    loadFiles();
  }, []);

  // Upload file
  const handleUpload = async (e) => {
    e.preventDefault();
    if (!selectedFile || uploading) return;

    setUploading(true);
    setStatusMsg(null);
    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const res = await fetch('/rag-upload', {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      if (data.files) {
        setFiles(data.files);
      } else {
        loadFiles();
      }
      setStatusMsg(data.message || 'File uploaded and indexed successfully.');
      setSelectedFile(null);
      // Reset input element
      const fileEl = document.getElementById('rag-file-input');
      if (fileEl) fileEl.value = '';
    } catch (err) {
      setStatusMsg(`Upload failed: ${err.message}`);
    } finally {
      setUploading(false);
    }
  };

  // Delete file
  const handleDelete = async (filename) => {
    if (!window.confirm(`Are you sure you want to delete '${filename}'?`)) return;

    try {
      const res = await fetch(`/rag-delete/${encodeURIComponent(filename)}`, {
        method: 'POST',
      });
      const data = await res.json();
      if (data.files) {
        setFiles(data.files);
      } else {
        loadFiles();
      }
      setStatusMsg(data.message || `Deleted ${filename}`);
    } catch (err) {
      setStatusMsg(`Delete failed: ${err.message}`);
    }
  };

  // Reindex all files
  const handleReindex = async () => {
    if (reindexing) return;
    setReindexing(true);
    setStatusMsg(null);
    try {
      const res = await fetch('/rag-reindex', { method: 'POST' });
      const data = await res.json();
      setStatusMsg(data.message || `Reindexed all files successfully.`);
      if (data.files) setFiles(data.files);
    } catch (err) {
      setStatusMsg(`Reindex failed: ${err.message}`);
    } finally {
      setReindexing(false);
    }
  };

  // Ask document query
  const handleQuery = async (e) => {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed || querying) return;

    const userMessage = { role: 'user', content: trimmed };
    setHistory((prev) => [...prev, userMessage]);
    setQuery('');
    setQuerying(true);
    setQueryError(null);

    try {
      const res = await fetch('/rag-query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: `query=${encodeURIComponent(trimmed)}`,
      });

      if (!res.ok) throw new Error(`Query failed (${res.status})`);
      const data = await res.json();

      const assistantMessage = {
        role: 'assistant',
        content: data.answer,
        sources: data.sources || [],
      };
      setHistory((prev) => [...prev, assistantMessage]);
    } catch (err) {
      setQueryError(err.message || 'Failed to query private documents.');
    } finally {
      setQuerying(false);
    }
  };

  // Reset conversation session
  const handleResetChat = async () => {
    try {
      await fetch('/rag-clear-history', { method: 'POST' });
    } catch (err) {
      console.error(err);
    }
    setHistory([]);
    setQueryError(null);
  };

  const getExtBadgeClass = (ext) => {
    if (ext === 'pdf') return 'ext-pdf';
    if (ext === 'xlsx' || ext === 'xls') return 'ext-excel';
    if (ext === 'csv') return 'ext-csv';
    return 'ext-text';
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* 1. Context Documents Card */}
      <div className="glass-card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
          <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#f4f4f5', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileText size={18} color="#60a5fa" /> Private Files & Policies in <code>/context</code>
          </h2>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleReindex}
            disabled={reindexing}
            style={{ fontSize: '0.8rem', padding: '6px 14px' }}
          >
            {reindexing ? <span className="spinner" /> : <RefreshCw size={13} />}
            <span>Re-index All</span>
          </button>
        </div>

        <p style={{ color: '#a1a1aa', fontSize: '0.85rem', lineHeight: '1.5', marginBottom: '14px' }}>
          Upload your documents, insurance policies, contracts, or spreadsheets. Supported: <strong>PDF, Excel (.xlsx, .xls), CSV, TXT, MD</strong>. Files are stored in <code>/context</code> and indexed into local ChromaDB vectors.
        </p>

        {/* Upload Form */}
        <form onSubmit={handleUpload} className="upload-row">
          <input
            id="rag-file-input"
            type="file"
            className="file-input"
            accept=".pdf,.xlsx,.xls,.csv,.txt,.md"
            onChange={(e) => setSelectedFile(e.target.files[0] || null)}
            disabled={uploading}
            required
          />
          <button type="submit" className="btn btn-primary" disabled={uploading || !selectedFile} style={{ fontSize: '0.85rem', padding: '9px 18px' }}>
            {uploading ? (
              <>
                <span className="spinner" /> Indexing File...
              </>
            ) : (
              <>
                <Upload size={14} /> Upload & Index
              </>
            )}
          </button>
        </form>

        {statusMsg && (
          <div style={{ marginTop: '12px', padding: '8px 12px', background: 'rgba(34, 197, 94, 0.12)', border: '1px solid rgba(34, 197, 94, 0.3)', color: '#4ade80', borderRadius: '8px', fontSize: '0.84rem' }}>
            {statusMsg}
          </div>
        )}

        {/* File List */}
        <div className="file-list">
          {loadingFiles && <div style={{ color: '#71717a', fontSize: '0.85rem', padding: '10px 0' }}>Loading indexed files...</div>}

          {!loadingFiles && files.length === 0 && (
            <div className="empty-state" style={{ padding: '20px 0' }}>
              No documents in <code>/context</code> yet. Upload a policy or spreadsheet above.
            </div>
          )}

          {files.map((f, idx) => (
            <div key={idx} className="file-item">
              <div className="file-info">
                <span className={`ext-badge ${getExtBadgeClass(f.ext)}`}>{f.ext}</span>
                <span className="file-name">{f.filename}</span>
                <span className="file-meta">({f.size_kb} KB &bull; {f.modified})</span>
              </div>
              <button
                type="button"
                className="btn-danger-ghost"
                onClick={() => handleDelete(f.filename)}
                title={`Delete ${f.filename}`}
              >
                <Trash2 size={12} style={{ marginRight: '4px', verticalAlign: 'middle' }} /> Delete
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* 2. Conversational Document Query Card (Chatbot Layout) */}
      <div className="glass-card chat-card-layout">
        <div className="chat-card-header">
          <h2 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#60a5fa', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <MessageSquare size={18} /> Document Q&A Conversation
          </h2>
          {history.length > 0 && (
            <button
              type="button"
              className="btn btn-danger-ghost"
              onClick={handleResetChat}
              title="Reset conversation session memory"
            >
              <Trash2 size={13} /> Reset Chat
            </button>
          )}
        </div>

        {/* Scrollable Conversation Thread */}
        <div className="chat-thread-container">
          {history.length === 0 && !querying && (
            <div className="empty-state" style={{ margin: 'auto 0', padding: '40px 20px', textAlign: 'center' }}>
              <div style={{ display: 'inline-flex', padding: '12px', background: 'rgba(59, 130, 246, 0.1)', borderRadius: '50%', marginBottom: '12px' }}>
                <FileText size={32} color="#60a5fa" />
              </div>
              <h3 style={{ color: '#f4f4f5', fontSize: '1.05rem', fontWeight: 600, marginBottom: '6px' }}>
                Ask Your Private Documents
              </h3>
              <p style={{ color: '#a1a1aa', fontSize: '0.86rem', maxWidth: '440px', margin: '0 auto', lineHeight: '1.6' }}>
                Ask any question across your uploaded files. Follow-ups, pronouns, comparisons, and policy citations will be answered with exact page references.
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
                    <Bot size={13} /> Document AI Specialist
                  </span>
                  <div className="assistant-bubble">
                    <div className="answer-body">{msg.content}</div>

                    {msg.sources && msg.sources.length > 0 && (
                      <details className="citations-box" open={idx === history.length - 1}>
                        <summary className="citations-summary">
                          {msg.sources.length} Document Citation(s) &dtrif;
                        </summary>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '8px' }}>
                          {msg.sources.map((s, sIdx) => (
                            <div key={sIdx} className="citation-card">
                              <div className="citation-header">
                                <span className="citation-doc">{s.source}</span>
                                <span className="citation-loc">{s.location}</span>
                              </div>
                              <div className="citation-quote">"{s.snippet}"</div>
                            </div>
                          ))}
                        </div>
                      </details>
                    )}
                  </div>
                </>
              )}
            </div>
          ))}

          {querying && (
            <div className="chat-turn chat-turn-assistant">
              <span className="chat-header-role">
                <Bot size={13} /> Document AI Specialist
              </span>
              <div className="assistant-bubble" style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#a1a1aa', fontSize: '0.88rem' }}>
                <span className="spinner" />
                <span>Searching ChromaDB vectors, resolving context, and synthesizing citations...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Error Notification */}
        {queryError && (
          <div style={{ marginBottom: '10px', padding: '10px 14px', background: 'rgba(239, 68, 68, 0.15)', border: '1px solid #ef4444', color: '#fca5a5', borderRadius: '8px', fontSize: '0.85rem' }}>
            {queryError}
          </div>
        )}

        {/* Bottom Input Form (Chatbot style) */}
        <div className="chat-input-wrapper">
          <form onSubmit={handleQuery} className="search-bar">
            <input
              type="text"
              className="search-input"
              placeholder="Ask anything across your uploaded files (e.g. Who is covered? What are the waiting periods?)..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              disabled={querying}
            />
            <button type="submit" className="btn btn-primary" disabled={querying || !query.trim()}>
              {querying ? (
                <>
                  <span className="spinner" /> Analyzing...
                </>
              ) : (
                <>
                  <Send size={15} /> Ask Documents
                </>
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
