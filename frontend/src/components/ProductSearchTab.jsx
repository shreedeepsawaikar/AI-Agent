import React, { useState } from 'react';
import { Search, ShoppingBag, ExternalLink, Tag } from 'lucide-react';

export default function ProductSearchTab() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [listings, setListings] = useState(null);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed || loading) return;

    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`/product-search?query=${encodeURIComponent(trimmed)}`);
      if (!res.ok) throw new Error(`Search failed (${res.status})`);
      const data = await res.json();
      setListings(data.listings || []);
    } catch (err) {
      setError(err.message || 'Product search failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="glass-card">
      <h2 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#60a5fa', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <ShoppingBag size={18} /> Indian Retail Product Search
      </h2>

      <form onSubmit={handleSubmit} className="search-bar">
        <input
          type="text"
          className="search-input"
          placeholder="e.g. Sony WH-1000XM5, iPhone 15, Running Shoes..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          disabled={loading}
          autoFocus
        />
        <button type="submit" className="btn btn-primary" disabled={loading || !query.trim()}>
          {loading ? (
            <>
              <span className="spinner" /> Scanning Stores...
            </>
          ) : (
            <>
              <Search size={15} /> Search Products
            </>
          )}
        </button>
      </form>

      {error && (
        <div style={{ marginTop: '14px', padding: '10px 14px', background: 'rgba(239, 68, 68, 0.15)', border: '1px solid #ef4444', color: '#fca5a5', borderRadius: '8px', fontSize: '0.85rem' }}>
          {error}
        </div>
      )}

      {/* Results */}
      {listings && (
        <div style={{ marginTop: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', color: '#a1a1aa', fontSize: '0.85rem' }}>
            <span>Found <strong>{listings.length}</strong> matching listing(s)</span>
          </div>

          {listings.length === 0 ? (
            <div className="empty-state">
              No products found for "{query}". Try a broader product name.
            </div>
          ) : (
            <div className="product-grid">
              {listings.map((item, idx) => (
                <div key={idx} className="product-item">
                  <div className="product-top-row">
                    <div style={{ flex: 1 }}>
                      <div className="product-title">{item.title}</div>
                      {item.snippet && (
                        <div className="product-desc">
                          {item.snippet.slice(0, 180)}
                          {item.snippet.length > 180 ? '...' : ''}
                        </div>
                      )}
                    </div>
                    {item.price && (
                      <div className="product-price">{item.price}</div>
                    )}
                  </div>
                  <div className="product-footer">
                    {item.store && (
                      <span className="store-badge">
                        <Tag size={11} style={{ marginRight: '4px', verticalAlign: 'middle' }} />
                        {item.store}
                      </span>
                    )}
                    {item.url && (
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="product-link"
                      >
                        Open Product Page <ExternalLink size={12} />
                      </a>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
