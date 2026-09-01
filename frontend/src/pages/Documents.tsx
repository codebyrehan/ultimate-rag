import { useState, useEffect, useCallback } from 'react';
import api from '../api';
import { DocumentResponse } from '../types';
import Header from '../components/Header';
import Sidebar from '../components/Sidebar';
import EmptyState from '../components/ui/EmptyState';
import { SkeletonCard } from '../components/ui/Skeleton';
import { useToast } from '../components/ui/Toast';

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const { addToast } = useToast();

  const fetchDocuments = useCallback(async () => {
    try {
      const res = await api.get('/documents/');
      setDocuments(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const handleUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    try {
      for (const file of Array.from(files)) {
        const form = new FormData();
        form.append('file', file);
        await api.post('/documents/upload', form, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
      }
      addToast('success', `${files.length} document${files.length > 1 ? 's' : ''} uploaded successfully`);
      await fetchDocuments();
    } catch (err: any) {
      addToast('error', err.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
      setDragOver(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this document?')) return;
    try {
      await api.delete(`/documents/${id}`);
      setDocuments(prev => prev.filter(d => d.id !== id));
      addToast('success', 'Document deleted successfully');
    } catch (err: any) {
      addToast('error', err.response?.data?.detail || 'Delete failed');
    }
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'indexed': return 'badge-success';
      case 'processing': return 'badge-warning';
      case 'failed': return 'badge-error';
      default: return 'badge-neutral';
    }
  };

  const filteredDocuments = documents.filter(doc => {
    const matchesSearch = doc.original_filename?.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         doc.filename.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesFilter = filterStatus === 'all' || doc.status.toLowerCase() === filterStatus;
    return matchesSearch && matchesFilter;
  });

  if (loading) {
    return (
      <div className="flex h-screen bg-[var(--color-bg-primary)]">
        <Sidebar />
        <div className="flex-1 flex flex-col overflow-hidden">
          <Header title="Documents" subtitle="Loading..." />
          <main className="flex-1 overflow-y-auto p-6 scrollbar-thin">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {[1, 2, 3, 4, 5, 6].map(i => (
                <SkeletonCard key={i} />
              ))}
            </div>
          </main>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-[var(--color-bg-primary)]">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header title="Documents" subtitle={`${documents.length} documents total`} />

        <main className="flex-1 overflow-y-auto p-6 scrollbar-thin">
          {/* Upload & Filters */}
          <div className="card p-6 mb-6">
            <div className="flex flex-col lg:flex-row gap-4 items-start lg:items-center justify-between">
              <div className="flex flex-col sm:flex-row gap-4 flex-1">
                <div className="relative flex-1 max-w-md">
                  <svg className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--color-text-tertiary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                  <input
                    type="text"
                    placeholder="Search documents..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="input pl-10"
                  />
                </div>
                <select
                  value={filterStatus}
                  onChange={(e) => setFilterStatus(e.target.value)}
                  className="input w-auto"
                >
                  <option value="all">All Status</option>
                  <option value="indexed">Indexed</option>
                  <option value="processing">Processing</option>
                  <option value="failed">Failed</option>
                </select>
              </div>

              <label
                className={`btn-primary cursor-pointer ${uploading ? 'opacity-50' : ''}`}
              >
                {uploading ? 'Uploading...' : 'Upload PDF'}
                <input
                  type="file"
                  accept="application/pdf"
                  multiple
                  onChange={(e) => handleUpload(e.target.files)}
                  className="hidden"
                  disabled={uploading}
                />
              </label>
            </div>
          </div>

          {/* Documents Grid */}
          {filteredDocuments.length === 0 ? (
            <div className="card p-12">
              <EmptyState
                icon="📄"
                title="No documents found"
                description={searchQuery ? 'Try adjusting your search or filter criteria.' : 'Upload your first PDF to get started.'}
              />
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredDocuments.map((doc) => (
                <div key={doc.id} className="card p-6 hover:shadow-lg transition-all duration-200 group">
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className="h-12 w-12 rounded-xl bg-red-50 dark:bg-red-900/20 flex items-center justify-center text-red-600 dark:text-red-400 group-hover:scale-110 transition-transform duration-200">
                        <svg className="h-6 w-6" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clipRule="evenodd" />
                        </svg>
                      </div>
                      <div className="min-w-0">
                        <h3 className="font-semibold text-[var(--color-text-primary)] line-clamp-1" title={doc.original_filename || doc.filename}>
                          {doc.original_filename || doc.filename}
                        </h3>
                        <p className="text-xs text-[var(--color-text-tertiary)] mt-0.5">
                          {doc.page_count} pages · {doc.chunks.length} chunks
                        </p>
                      </div>
                    </div>
                    <span className={`badge ${getStatusColor(doc.status)}`}>
                      {doc.status}
                    </span>
                  </div>

                  <div className="space-y-2 mb-4">
                    <div className="flex justify-between text-sm">
                      <span className="text-[var(--color-text-secondary)]">SHA-256</span>
                      <span className="text-[var(--color-text-primary)] font-mono text-xs">
                        {doc.sha256.slice(0, 16)}...
                      </span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-[var(--color-text-secondary)]">Version</span>
                      <span className="text-[var(--color-text-primary)]">{doc.version}</span>
                    </div>
                    {doc.created_at && (
                      <div className="flex justify-between text-sm">
                        <span className="text-[var(--color-text-secondary)]">Created</span>
                        <span className="text-[var(--color-text-primary)]">
                          {new Date(doc.created_at).toLocaleDateString()}
                        </span>
                      </div>
                    )}
                  </div>

                  <div className="flex gap-2">
                    <a
                      href={`/documents/${doc.id}`}
                      className="btn-secondary flex-1 text-center text-sm py-1.5"
                    >
                      View Details
                    </a>
                    <button
                      onClick={() => handleDelete(doc.id)}
                      className="btn-secondary text-red-600 hover:text-red-700 hover:border-red-300 text-sm py-1.5 px-3"
                    >
                      <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
