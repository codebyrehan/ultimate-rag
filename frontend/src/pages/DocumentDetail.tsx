import { useParams } from 'react-router-dom';
import { useEffect, useState } from 'react';
import api from '../api';
import { DocumentResponse } from '../types';
import PdfViewer from '../components/PdfViewer';
import Header from '../components/Header';
import Sidebar from '../components/Sidebar';
import { Skeleton } from '../components/ui/Skeleton';
import EmptyState from '../components/ui/EmptyState';
import { useToast } from '../components/ui/Toast';

export default function DocumentDetailPage() {
  const { documentId } = useParams<{ documentId: string }>();
  const [doc, setDoc] = useState<DocumentResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const { addToast } = useToast();

  useEffect(() => {
    if (documentId) {
      api
        .get(`/documents/${documentId}`)
        .then((res) => setDoc(res.data))
        .catch(err => addToast('error', 'Failed to load document'))
        .finally(() => setLoading(false));
    }
  }, [documentId, addToast]);

  if (loading) {
    return (
      <div className="flex h-screen bg-[var(--color-bg-primary)]">
        <Sidebar />
        <div className="flex-1 flex flex-col overflow-hidden">
          <Header title="Document Details" subtitle="Loading..." />
          <main className="flex-1 overflow-y-auto p-6 scrollbar-thin">
            <div className="max-w-6xl mx-auto space-y-6">
              <div className="card p-6">
                <Skeleton className="h-8 w-3/4 rounded mb-4" />
                <Skeleton className="h-4 w-1/2 rounded" />
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6">
                  {[1, 2, 3, 4].map(i => (
                    <Skeleton key={i} className="h-24 rounded-lg" />
                  ))}
                </div>
              </div>
              <div className="card p-6">
                <Skeleton className="h-64 rounded-lg" />
              </div>
            </div>
          </main>
        </div>
      </div>
    );
  }

  if (!doc) {
    return (
      <div className="flex h-screen bg-[var(--color-bg-primary)]">
        <Sidebar />
        <div className="flex-1 flex items-center justify-center">
          <EmptyState
            icon="📄"
            title="Document not found"
            description="The document you're looking for doesn't exist or has been deleted."
          />
        </div>
      </div>
    );
  }

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'indexed': return 'badge-success';
      case 'processing': return 'badge-warning';
      case 'failed': return 'badge-error';
      default: return 'badge-neutral';
    }
  };

  return (
    <div className="flex h-screen bg-[var(--color-bg-primary)]">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header title="Document Details" subtitle={doc.original_filename || doc.filename} />

        <main className="flex-1 overflow-y-auto p-6 scrollbar-thin">
          <div className="max-w-6xl mx-auto">
            {/* Document Info */}
            <div className="card p-6 mb-6">
              <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 mb-6">
                <div className="flex items-start gap-4">
                  <div className="h-14 w-14 rounded-xl bg-red-50 dark:bg-red-900/20 flex items-center justify-center text-red-600 dark:text-red-400 shrink-0">
                    <svg className="h-7 w-7" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clipRule="evenodd" />
                    </svg>
                  </div>
                  <div>
                    <h2 className="text-2xl font-bold text-[var(--color-text-primary)]">
                      {doc.original_filename || doc.filename}
                    </h2>
                    <p className="text-[var(--color-text-secondary)] mt-1">
                      Document ID: <code className="text-xs bg-[var(--color-bg-secondary)] px-2 py-1 rounded font-mono">{doc.id}</code>
                    </p>
                  </div>
                </div>
                <span className={`badge ${getStatusColor(doc.status)} text-sm px-3 py-1`}>{doc.status}</span>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <InfoCard label="Pages" value={doc.page_count.toString()} icon="📄" />
                <InfoCard label="Chunks" value={doc.chunks.length.toString()} icon="🧩" />
                <InfoCard label="Version" value={doc.version.toString()} icon="🔖" />
                <InfoCard label="Indexing" value={doc.indexing_status} icon="⚡" />
              </div>

              <div className="mb-6">
                <h3 className="text-sm font-semibold text-[var(--color-text-secondary)] mb-2 uppercase tracking-wider">SHA-256 Checksum</h3>
                <code className="text-xs bg-[var(--color-bg-secondary)] p-3 rounded-lg block overflow-x-auto font-mono border border-[var(--color-border)]">
                  {doc.sha256}
                </code>
              </div>

              {doc.chunks.length > 0 && (
                <div>
                  <h3 className="text-lg font-semibold text-[var(--color-text-primary)] mb-4">
                    Chunks ({doc.chunks.length})
                  </h3>
                  <div className="space-y-2 max-h-64 overflow-y-auto scrollbar-thin">
                    {doc.chunks.map((chunk) => (
                      <div key={chunk.id} className="p-4 bg-[var(--color-bg-secondary)] rounded-lg border border-[var(--color-border)] hover:border-[var(--color-accent)] transition-colors duration-200">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-sm text-[var(--color-text-primary)]">
                              Chunk {chunk.id.slice(0, 8)}
                            </span>
                            {chunk.section && (
                              <span className="badge badge-neutral text-xs">{chunk.section}</span>
                            )}
                          </div>
                          <span className="text-xs text-[var(--color-text-tertiary)]">
                            Page {chunk.page_number}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* PDF Preview */}
            <div className="card p-6">
              <h3 className="text-lg font-semibold text-[var(--color-text-primary)] mb-4">Document Preview</h3>
              <PdfViewer
                documentId={doc.id}
                filename={doc.original_filename || doc.filename}
                pageCount={doc.page_count}
              />
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

function InfoCard({ label, value, icon }: { label: string; value: string; icon: string }) {
  return (
    <div className="p-4 bg-[var(--color-bg-secondary)] rounded-xl border border-[var(--color-border)] hover:border-[var(--color-accent)] transition-colors duration-200">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-sm">{icon}</span>
        <p className="text-xs font-medium text-[var(--color-text-secondary)] uppercase tracking-wider">{label}</p>
      </div>
      <p className="text-lg font-semibold text-[var(--color-text-primary)]">{value}</p>
    </div>
  );
}
