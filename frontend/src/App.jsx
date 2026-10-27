import React, { useState } from 'react';
import Header from './components/Header';
import Tabs from './components/Tabs';
import WebResearchTab from './components/WebResearchTab';
import ProductSearchTab from './components/ProductSearchTab';
import MultiStepTab from './components/MultiStepTab';
import DocumentRagTab from './components/DocumentRagTab';

export default function App() {
  const [activeTab, setActiveTab] = useState('research');

  return (
    <div className="app-container">
      <Header />
      <Tabs activeTab={activeTab} onSelectTab={setActiveTab} />

      <main>
        {activeTab === 'research' && <WebResearchTab />}
        {activeTab === 'products' && <ProductSearchTab />}
        {activeTab === 'multistep' && <MultiStepTab />}
        {activeTab === 'rag' && <DocumentRagTab />}
      </main>
    </div>
  );
}
