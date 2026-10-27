import React from 'react';
import { Sparkles, Globe, ShoppingBag, Layers, FileText } from 'lucide-react';

export default function Header() {
  return (
    <header className="app-header">
      <h1 className="app-title">AI Research & Document RAG</h1>
      <div className="app-subtitle">
        <span className="pill-tag"><Globe size={13} /> Web Research</span>
        <span className="pill-tag"><ShoppingBag size={13} /> Indian Retail</span>
        <span className="pill-tag"><Layers size={13} /> Multi-Step Planner</span>
        <span className="pill-tag"><FileText size={13} /> Private Policy RAG</span>
      </div>
    </header>
  );
}
