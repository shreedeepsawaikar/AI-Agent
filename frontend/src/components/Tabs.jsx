import React from 'react';
import { Globe, ShoppingBag, Layers, FileText } from 'lucide-react';

const TABS = [
  { id: 'research', label: 'Web Research', icon: Globe },
  { id: 'products', label: 'Product Search', icon: ShoppingBag },
  { id: 'multistep', label: 'Multi-Step', icon: Layers },
  { id: 'rag', label: 'Document / Context RAG', icon: FileText },
];

export default function Tabs({ activeTab, onSelectTab }) {
  return (
    <nav className="tab-bar">
      {TABS.map((tab) => {
        const Icon = tab.icon;
        const isActive = activeTab === tab.id;
        return (
          <button
            key={tab.id}
            type="button"
            className={`tab-btn ${isActive ? 'active' : ''}`}
            onClick={() => onSelectTab(tab.id)}
          >
            <Icon size={16} />
            <span>{tab.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
