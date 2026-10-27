import React, { useState } from 'react';
import { Layers, CheckCircle2, ArrowRight, Play, RefreshCw } from 'lucide-react';

export default function MultiStepTab() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [approving, setApproving] = useState(false);
  const [state, setState] = useState(null); // { query, sub_questions, raw_search }
  const [finalAnswer, setFinalAnswer] = useState(null);
  const [error, setError] = useState(null);

  const handleStart = async (e) => {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed || loading) return;

    setLoading(true);
    setError(null);
    setState(null);
    setFinalAnswer(null);

    try {
      const res = await fetch(`/multi-step?query=${encodeURIComponent(trimmed)}`);
      if (!res.ok) throw new Error(`Multi-step planning failed (${res.status})`);
      const data = await res.json();
      setState(data);
    } catch (err) {
      setError(err.message || 'Failed to execute multi-step research.');
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async () => {
    if (approving) return;
    setApproving(true);
    setError(null);

    try {
      const res = await fetch('/multi-step-approve', { method: 'POST' });
      if (!res.ok) throw new Error(`Synthesis failed (${res.status})`);
      const data = await res.json();
      setFinalAnswer(data.answer);
    } catch (err) {
      setError(err.message || 'Approval synthesis failed.');
    } finally {
      setApproving(false);
    }
  };

  const handleReset = () => {
    setQuery('');
    setState(null);
    setFinalAnswer(null);
    setError(null);
  };

  return (
    <div className="glass-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <h2 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#60a5fa', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Layers size={18} /> Multi-Step Agent (LangGraph Planner)
        </h2>
        {(state || finalAnswer) && (
          <button type="button" className="btn btn-secondary" onClick={handleReset} style={{ fontSize: '0.8rem', padding: '6px 12px' }}>
            <RefreshCw size={13} /> New Multi-Step
          </button>
        )}
      </div>

      {!state && !finalAnswer && (
        <form onSubmit={handleStart} className="search-bar">
          <input
            type="text"
            className="search-input"
            placeholder="e.g. Impact of artificial intelligence on healthcare diagnostics over next 5 years..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={loading}
            autoFocus
          />
          <button type="submit" className="btn btn-primary" disabled={loading || !query.trim()}>
            {loading ? (
              <>
                <span className="spinner" /> Planning & Researching...
              </>
            ) : (
              <>
                <Play size={15} /> Start Multi-Step
              </>
            )}
          </button>
        </form>
      )}

      {error && (
        <div style={{ marginTop: '14px', padding: '10px 14px', background: 'rgba(239, 68, 68, 0.15)', border: '1px solid #ef4444', color: '#fca5a5', borderRadius: '8px', fontSize: '0.85rem' }}>
          {error}
        </div>
      )}

      {/* Progress Tracker */}
      {(state || finalAnswer) && (
        <div className="tracker-box" style={{ marginTop: '18px' }}>
          <div className="tracker-row">
            <span className="step-pill step-pill-done">STEP 1</span>
            <span className="step-title" style={{ color: '#93c5fd' }}>Break down query into targeted sub-questions</span>
            <span className="step-status" style={{ color: '#34d399' }}><CheckCircle2 size={15} style={{ verticalAlign: 'middle' }} /> Done</span>
          </div>
          <div className="tracker-row">
            <span className="step-pill step-pill-done">STEP 2</span>
            <span className="step-title" style={{ color: '#93c5fd' }}>Research each sub-topic in parallel</span>
            <span className="step-status" style={{ color: '#34d399' }}><CheckCircle2 size={15} style={{ verticalAlign: 'middle' }} /> Done</span>
          </div>
          <div className="tracker-row">
            <span className={`step-pill ${finalAnswer ? 'step-pill-done' : 'step-pill-active'}`}>STEP 3</span>
            <span className="step-title" style={{ color: finalAnswer ? '#93c5fd' : '#f59e0b' }}>
              {finalAnswer ? 'Approved by you' : 'Review findings & human approval'}
            </span>
            <span className="step-status" style={{ color: finalAnswer ? '#34d399' : '#f59e0b' }}>
              {finalAnswer ? <CheckCircle2 size={15} style={{ verticalAlign: 'middle' }} /> : '← Pending Approval'}
            </span>
          </div>
          {finalAnswer && (
            <div className="tracker-row">
              <span className="step-pill step-pill-finished">COMPLETE</span>
              <span className="step-title" style={{ color: '#34d399', fontWeight: 600 }}>Synthesized Executive Report</span>
              <span className="step-status" style={{ color: '#34d399' }}><CheckCircle2 size={15} style={{ verticalAlign: 'middle' }} /> Ready</span>
            </div>
          )}
        </div>
      )}

      {/* Step 3: Pending Approval Details */}
      {state && !finalAnswer && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ background: 'rgba(20,20,26,0.7)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '12px', padding: '16px' }}>
            <h4 style={{ color: '#60a5fa', fontSize: '0.95rem', marginBottom: '10px' }}>Sub-questions generated</h4>
            <ol style={{ paddingLeft: '20px', color: '#d4d4d8', fontSize: '0.9rem', lineHeight: '1.7' }}>
              {state.sub_questions && state.sub_questions.map((q, idx) => (
                <li key={idx}>{q}</li>
              ))}
            </ol>
          </div>

          <div style={{ background: 'rgba(20,20,26,0.7)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '12px', padding: '16px' }}>
            <h4 style={{ color: '#60a5fa', fontSize: '0.95rem', marginBottom: '10px' }}>Raw Search Evidence</h4>
            <pre style={{ color: '#a1a1aa', fontSize: '0.8rem', lineHeight: '1.6', whiteSpace: 'pre-wrap', maxHeight: '280px', overflowY: 'auto' }}>
              {state.raw_search}
            </pre>
          </div>

          <button
            type="button"
            className="btn btn-success"
            onClick={handleApprove}
            disabled={approving}
          >
            {approving ? (
              <>
                <span className="spinner" /> Synthesizing Final Answer...
              </>
            ) : (
              <>
                Approve & Synthesize Final Answer <ArrowRight size={16} />
              </>
            )}
          </button>
        </div>
      )}

      {/* Step 4: Final Synthesized Report */}
      {finalAnswer && (
        <div style={{ background: 'rgba(20,20,26,0.85)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '14px', padding: '22px', marginTop: '14px' }}>
          <h3 style={{ color: '#60a5fa', fontSize: '1.1rem', marginBottom: '12px' }}>Executive Synthesis</h3>
          <div style={{ color: '#f4f4f5', lineHeight: '1.8', fontSize: '0.95rem', whiteSpace: 'pre-wrap' }}>
            {finalAnswer}
          </div>
        </div>
      )}
    </div>
  );
}
