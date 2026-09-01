import { useParams } from 'react-router-dom';
import { useEffect, useState } from 'react';
import api from '../api';
import { DocumentResponse } from '../types';
import PdfViewer from '../components/PdfViewer';
import Header from '../components/Header';
import Sidebar from '../components/Sidebar';

export default function DocumentDetailPage() {
  const { documentId } = useParams<{ documentId: string }>();
  const [doc, setDoc] = useState<DocumentResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (documentId) {
      api
        .get(`/documents/${documentId}`)
        .then((res) => setDoc(res.data))
        .catch(console.error)
        .finally(() => setLoading(false));
    }
  }, [documentId]);

  if (loading) {
    return (
      <div className="flex h-screen bg-[var(--color-bg-primary)]">
        <Sidebar />
        <div className="flex-1 flex items-center justify-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[var(--color-accent)]"></div>
        </div>
      </div>
    );
  }

  if (!doc) {
    return (
      <div className="flex h-screen bg-[var(--color-bg-primary)]">
        <Sidebar />
        <div className="flex-1 flex items-center justify-center">
          <p className="text-[var(--color-text-secondary)]">Document not found.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-[var(--color-bg-primary)]">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header title="Document Details" subtitle={doc.original_filename || doc.filename} />

        <main className="flex-1 overflow-y-auto p-6 scrollbar-thin">
          <div className="max-w-6xl mx-auto">
            <div className="card p-6 mb-6">
              <div className="flex items-start justify-between mb-6">
                <div>
                  <h2 className="text-2xl font-bold text-[var(--color-text-primary)]">
                    {doc.original_filename || doc.filename}
                  </h2>
                  <p className="text-[var(--color-text-secondary)] mt-1">
                    Document ID: <code className="text-xs bg-[var(--color-bg-secondary)] px-2 py-1 rounded">{doc.id}</code>
                  </p>
                </div>
                <span className={`badge ${doc.status === 'indexed' ? 'badge-success' : doc.status === 'failed' ? 'badge-error' : 'badge-warning'}`}>
                  {doc.status}
                </span>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <InfoCard label="Pages" value={doc.page_count.toString()} />
                <InfoCard label="Chunks" value={doc.chunks.length.toString()} />
                <InfoCard label="Version" value={doc.version.toString()} />
                <InfoCard label="Indexing" value={doc.indexing_status} />
              </div>

              <div className="mb-6">
                <h3 className="text-sm font-medium text-[var(--color-text-secondary)] mb-2">SHA-256</h3>
                <code className="text-xs bg-[var(--color-bg-secondary)] p-2 rounded block overflow-x-auto">
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
                      <div key={chunk.id} className="p-3 bg-[var(--color-bg-secondary)] rounded-lg border border-[var(--color-border)]">
                        <div className="flex items-center justify-between">
                          <span className="font-medium text-sm text-[var(--color-text-primary)]">
                            Chunk {chunk.id.slice(0, 8)}
                          </span>
                          <span className="text-xs text-[var(--color-text-tertiary)]">
                            Page {chunk.page_number}
                            {chunk.section && ` · ${chunk.section}`}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

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

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="p-4 bg-[var(--color-bg-secondary)] rounded-lg border border-[var(--color-border)]">
      <p className="text-xs font-medium text-[var(--color-text-secondary)] mb-1">{label}</p>
      <p className="text-lg font-semibold text-[var(--color-text-primary)]">{value}</p>
    </div>
  );
}
