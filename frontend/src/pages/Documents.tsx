import { useState, useEffect } from 'react';
import api from '../api';
import { DocumentResponse } from '../types';
import Header from '../components/Header';
import Sidebar from '../components/Sidebar';

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState<string>('all');

  useEffect(() => {
    fetchDocuments();
  }, []);

  async function fetchDocuments() {
    try {
      const res = await api.get('/documents/');
      setDocuments(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    setUploading(true);
    setUploadError(null);
    try {
      for (const file of Array.from(files)) {
        const form = new FormData();
        form.append('file', file);
        await api.post('/documents/upload', form, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
      }
      await fetchDocuments();
    } catch (err: any) {
      setUploadError(err.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this document?')) return;
    try {
      await api.delete(`/documents/${id}`);
      setDocuments(prev => prev.filter(d => d.id !== id));
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Delete failed');
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
        <div className="flex-1 flex items-center justify-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-[var(--color-accent)]"></div>
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
          {uploadError && (
            <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-800 dark:text-red-200">
              {uploadError}
            </div>
          )}

          {/* Upload & Filters */}
          <div className="card p-6 mb-6">
            <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
              <div className="flex gap-4 flex-1">
                <div className="flex-1 max-w-md">
                  <input
                    type="text"
                    placeholder="Search documents..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="input-field"
                  />
                </div>
                <select
                  value={filterStatus}
                  onChange={(e) => setFilterStatus(e.target.value)}
                  className="input-field w-auto"
                >
                  <option value="all">All Status</option>
                  <option value="indexed">Indexed</option>
                  <option value="processing">Processing</option>
                  <option value="failed">Failed</option>
                </select>
              </div>

              <label className="btn-primary cursor-pointer">
                {uploading ? 'Uploading...' : 'Upload PDF'}
                <input
                  type="file"
                  accept="application/pdf"
                  multiple
                  onChange={handleUpload}
                  className="hidden"
                  disabled={uploading}
                />
              </label>
            </div>
          </div>

          {/* Documents Grid */}
          {filteredDocuments.length === 0 ? (
            <div className="card p-12 text-center">
              <div className="text-6xl mb-4">📄</div>
              <h3 className="text-lg font-semibold text-[var(--color-text-primary)] mb-2">No documents found</h3>
              <p className="text-[var(--color-text-secondary)]">
                {searchQuery ? 'Try adjusting your search or filter criteria.' : 'Upload your first PDF to get started.'}
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredDocuments.map((doc) => (
                <div key={doc.id} className="card p-6 hover:shadow-md transition-shadow duration-200">
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className="p-2 bg-red-50 dark:bg-red-900/20 rounded-lg">
                        <span className="text-2xl">📄</span>
                      </div>
                      <div>
                        <h3 className="font-medium text-[var(--color-text-primary)] line-clamp-1" title={doc.original_filename || doc.filename}>
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
                      Delete
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
