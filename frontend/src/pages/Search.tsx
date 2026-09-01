import { useState } from 'react';
import api from '../api';
import { Citation } from '../types';
import Header from '../components/Header';
import Sidebar from '../components/Sidebar';

interface SearchResponse {
  query_id: string;
  conversation_id?: string | null;
  answer: string;
  confidence: number;
  model: string;
  citations: Citation[];
  verified: boolean;
  supported_fraction: number;
}

export default function SearchPage() {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || loading) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await api.post('/search/query', { query });
      setResult(res.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Search failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen bg-[var(--color-bg-primary)]">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header title="Search" subtitle="Hybrid semantic + keyword search across your documents" />

        <main className="flex-1 overflow-y-auto p-6 scrollbar-thin">
          <div className="max-w-4xl mx-auto">
            <form onSubmit={handleSearch} className="mb-8">
              <div className="flex gap-3">
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search your documents..."
                  className="input-field flex-1"
                  disabled={loading}
                />
                <button
                  type="submit"
                  disabled={loading || !query.trim()}
                  className="btn-primary px-8 disabled:opacity-50"
                >
                  {loading ? 'Searching...' : 'Search'}
                </button>
              </div>
            </form>

            {error && (
              <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-800 dark:text-red-200">
                {error}
              </div>
            )}

            {result && (
              <div className="space-y-6">
                {/* Answer Card */}
                <div className="card p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-semibold text-[var(--color-text-primary)]">Answer</h3>
                    <div className="flex items-center gap-4 text-sm">
                      <span className="text-[var(--color-text-secondary)]">
                        Confidence: {(result.confidence * 100).toFixed(0)}%
                      </span>
                      <span className={`badge ${result.verified ? 'badge-success' : 'badge-warning'}`}>
                        {result.verified ? 'Verified' : 'Unverified'}
                      </span>
                    </div>
                  </div>
                  <div className="prose dark:prose-invert max-w-none">
                    <p className="text-[var(--color-text-primary)] whitespace-pre-wrap leading-relaxed">
                      {result.answer}
                    </p>
                  </div>
                </div>

                {/* Citations */}
                {result.citations.length > 0 && (
                  <div className="card p-6">
                    <h3 className="text-lg font-semibold text-[var(--color-text-primary)] mb-4">
                      Sources ({result.citations.length})
                    </h3>
                    <div className="space-y-4">
                      {result.citations.map((citation, idx) => (
                        <div key={idx} className="p-4 bg-[var(--color-bg-secondary)] rounded-lg border border-[var(--color-border)]">
                          <div className="flex items-center justify-between mb-2">
                            <span className="font-medium text-[var(--color-text-primary)]">
                              [{idx + 1}] {citation.doc_filename}
                            </span>
                            <span className="text-sm text-[var(--color-text-tertiary)]">
                              Page {citation.page_number}
                            </span>
                          </div>
                          <p className="text-sm text-[var(--color-text-secondary)] mb-3 line-clamp-3">
                            {citation.label}
                          </p>
                          <div className="flex items-center justify-between text-sm">
                            <div className="flex items-center gap-4">
                              <span className="text-[var(--color-text-tertiary)]">
                                Score: {(citation.score * 100).toFixed(0)}%
                              </span>
                              {citation.verified ? (
                                <span className="text-green-600 dark:text-green-400">✓ Verified</span>
                              ) : (
                                <span className="text-amber-600 dark:text-amber-400">⚠ Unverified</span>
                              )}
                            </div>
                            <span className="text-xs text-[var(--color-text-tertiary)]">
                              Supported: {(citation.supported_fraction * 100).toFixed(0)}%
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {!result && !loading && !error && (
              <div className="text-center py-16">
                <div className="text-6xl mb-4">🔍</div>
                <h3 className="text-lg font-semibold text-[var(--color-text-primary)] mb-2">Search your documents</h3>
                <p className="text-[var(--color-text-secondary)] max-w-md mx-auto">
                  Use natural language to search across all your uploaded documents. Get AI-powered answers with citations.
                </p>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
