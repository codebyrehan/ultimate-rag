import { useState } from 'react';
import api from '../api';
import { Citation } from '../types';
import Header from '../components/Header';
import Sidebar from '../components/Sidebar';
import EmptyState from '../components/ui/EmptyState';
import { useToast } from '../components/ui/Toast';

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
  const { addToast } = useToast();

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
      const message = err.response?.data?.detail || 'Search failed';
      setError(message);
      addToast('error', message);
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
              <div className="relative">
                <svg className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-[var(--color-text-tertiary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search your documents with natural language..."
                  className="input pl-12 pr-32"
                  disabled={loading}
                />
                <button
                  type="submit"
                  disabled={loading || !query.trim()}
                  className="absolute right-2 top-1/2 -translate-y-1/2 btn-primary px-6 disabled:opacity-50"
                >
                  {loading ? (
                    <span className="flex items-center gap-2">
                      <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      Searching...
                    </span>
                  ) : 'Search'}
                </button>
              </div>
            </form>

            {error && (
              <div className="mb-6 p-4 rounded-lg border border-[var(--color-error)] bg-[var(--color-error-light)] text-[var(--color-error)]">
                <div className="flex items-center gap-2">
                  <svg className="h-5 w-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <p className="text-sm font-medium">{error}</p>
                </div>
              </div>
            )}

            {result && (
              <div className="space-y-6 animate-in">
                {/* Answer Card */}
                <div className="card p-6">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
                    <h3 className="text-lg font-semibold">Answer</h3>
                    <div className="flex items-center gap-3">
                      <span className="text-sm text-[var(--color-text-secondary)]">
                        Confidence: {(result.confidence * 100).toFixed(0)}%
                      </span>
                      <span className={`badge ${result.verified ? 'badge-success' : 'badge-warning'}`}>
                        {result.verified ? '✓ Verified' : '⚠ Unverified'}
                      </span>
                    </div>
                  </div>
                  <div className="prose dark:prose-invert max-w-none">
                    <p className="text-[var(--color-text-primary)] whitespace-pre-wrap leading-relaxed text-base">
                      {result.answer}
                    </p>
                  </div>
                </div>

                {/* Citations */}
                {result.citations.length > 0 && (
                  <div className="card p-6">
                    <h3 className="text-lg font-semibold mb-4">
                      Sources ({result.citations.length})
                    </h3>
                    <div className="space-y-4">
                      {result.citations.map((citation, idx) => (
                        <div key={idx} className="p-4 bg-[var(--color-bg-secondary)] rounded-xl border border-[var(--color-border)] hover:border-[var(--color-accent)] transition-colors duration-200">
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
                                <span className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">✓ Verified</span>
                              ) : (
                                <span className="text-xs text-amber-600 dark:text-amber-400 font-medium">⚠ Unverified</span>
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
                <EmptyState
                  icon="🔍"
                  title="Search your documents"
                  description="Use natural language to search across all your uploaded documents. Get AI-powered answers with citations."
                />
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
