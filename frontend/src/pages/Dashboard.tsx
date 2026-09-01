import { useState, useEffect } from 'react';
import api from '../api';
import { DocumentResponse, ConversationResponse, JobResponse } from '../types';
import Header from '../components/Header';
import Sidebar from '../components/Sidebar';

interface Stats {
  documents: number;
  chunks: number;
  jobs: number;
  conversations: number;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<Stats>({ documents: 0, chunks: 0, jobs: 0, conversations: 0 });
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [conversations, setConversations] = useState<ConversationResponse[]>([]);
  const [jobs, setJobs] = useState<JobResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  useEffect(() => {
    fetchData();
  }, []);

  async function fetchData() {
    setLoading(true);
    try {
      const [docsRes, convRes, jobsRes] = await Promise.all([
        api.get('/documents/'),
        api.get('/conversations/'),
        api.get('/jobs/'),
      ]);

      const docs = docsRes.data;
      const totalChunks = docs.reduce((sum: number, doc: DocumentResponse) => sum + doc.chunks.length, 0);

      setStats({
        documents: docs.length,
        chunks: totalChunks,
        jobs: jobsRes.data.length,
        conversations: convRes.data.length,
      });
      setDocuments(docs.slice(0, 10));
      setConversations(convRes.data.slice(0, 10));
      setJobs(jobsRes.data.slice(0, 10));
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
      await fetchData();
    } catch (err: any) {
      setUploadError(err.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'indexed':
        return 'badge-success';
      case 'processing':
        return 'badge-warning';
      case 'failed':
        return 'badge-error';
      default:
        return 'badge-neutral';
    }
  };

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
        <Header title="Dashboard" subtitle="Welcome back! Here's what's happening with your documents." />

        <main className="flex-1 overflow-y-auto p-6 scrollbar-thin">
          {uploadError && (
            <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-800 dark:text-red-200">
              {uploadError}
            </div>
          )}

          {/* Stats Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <StatCard title="Documents" value={stats.documents} icon="📄" color="blue" />
            <StatCard title="Indexed Chunks" value={stats.chunks} icon="🧩" color="emerald" />
            <StatCard title="Processing Jobs" value={stats.jobs} icon="⚙️" color="amber" />
            <StatCard title="Conversations" value={stats.conversations} icon="💬" color="purple" />
          </div>

          {/* Upload Section */}
          <div className="card p-6 mb-8">
            <h3 className="text-lg font-semibold text-[var(--color-text-primary)] mb-4">Upload Document</h3>
            <label className="flex flex-col items-center justify-center w-full h-32 border-2 border-dashed border-[var(--color-border)] rounded-lg cursor-pointer hover:border-[var(--color-accent)] transition-colors duration-200">
              <div className="flex flex-col items-center justify-center pt-5 pb-6">
                <svg className="w-8 h-8 mb-2 text-[var(--color-text-tertiary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
                <p className="text-sm text-[var(--color-text-secondary)]">
                  {uploading ? 'Uploading...' : 'Click to upload or drag and drop PDF'}
                </p>
              </div>
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

          {/* Recent Documents */}
          <div className="card p-6 mb-8">
            <h3 className="text-lg font-semibold text-[var(--color-text-primary)] mb-4">Recent Documents</h3>
            {documents.length === 0 ? (
              <p className="text-[var(--color-text-tertiary)] text-center py-8">No documents uploaded yet.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-[var(--color-border)]">
                  <thead>
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-[var(--color-text-secondary)] uppercase tracking-wider">Name</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-[var(--color-text-secondary)] uppercase tracking-wider">Status</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-[var(--color-text-secondary)] uppercase tracking-wider">Pages</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-[var(--color-text-secondary)] uppercase tracking-wider">Chunks</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-[var(--color-text-secondary)] uppercase tracking-wider">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--color-border)]">
                    {documents.map((doc) => (
                      <tr key={doc.id} className="hover:bg-[var(--color-bg-secondary)] transition-colors duration-150">
                        <td className="px-4 py-3 text-sm font-medium text-[var(--color-text-primary)]">
                          {doc.original_filename || doc.filename}
                        </td>
                        <td className="px-4 py-3">
                          <span className={`badge ${getStatusColor(doc.status)}`}>
                            {doc.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm text-[var(--color-text-secondary)]">{doc.page_count}</td>
                        <td className="px-4 py-3 text-sm text-[var(--color-text-secondary)]">{doc.chunks.length}</td>
                        <td className="px-4 py-3 text-sm">
                          <a href={`/documents/${doc.id}`} className="text-[var(--color-accent)] hover:text-[var(--color-accent-hover)] font-medium">
                            View
                          </a>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Recent Conversations */}
          <div className="card p-6 mb-8">
            <h3 className="text-lg font-semibold text-[var(--color-text-primary)] mb-4">Recent Conversations</h3>
            {conversations.length === 0 ? (
              <p className="text-[var(--color-text-tertiary)] text-center py-8">No conversations yet.</p>
            ) : (
              <div className="space-y-3">
                {conversations.map((conv) => (
                  <a
                    key={conv.id}
                    href={`/chat/${conv.id}`}
                    className="flex items-center justify-between p-4 rounded-lg bg-[var(--color-bg-secondary)] hover:bg-[var(--color-bg-tertiary)] transition-colors duration-200"
                  >
                    <div>
                      <p className="font-medium text-[var(--color-text-primary)]">{conv.title || 'Untitled Conversation'}</p>
                      <p className="text-sm text-[var(--color-text-secondary)]">{conv.messages.length} messages</p>
                    </div>
                    <span className="text-xs text-[var(--color-text-tertiary)]">
                      {new Date(conv.updated_at).toLocaleDateString()}
                    </span>
                  </a>
                ))}
              </div>
            )}
          </div>

          {/* Recent Jobs */}
          <div className="card p-6">
            <h3 className="text-lg font-semibold text-[var(--color-text-primary)] mb-4">Processing Jobs</h3>
            {jobs.length === 0 ? (
              <p className="text-[var(--color-text-tertiary)] text-center py-8">No jobs.</p>
            ) : (
              <div className="space-y-3">
                {jobs.map((job) => (
                  <div key={job.id} className="flex items-center justify-between p-4 rounded-lg bg-[var(--color-bg-secondary)]">
                    <div>
                      <p className="font-medium text-[var(--color-text-primary)]">{job.kind}</p>
                      <p className="text-sm text-[var(--color-text-secondary)]">Job ID: {job.id.slice(0, 12)}...</p>
                      {job.error && <p className="text-sm text-red-600 mt-1">{job.error}</p>}
                    </div>
                    <span className={`badge ${getStatusColor(job.status)}`}>
                      {job.status}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}

function StatCard({ title, value, icon, color }: { title: string; value: number; icon: string; color: string }) {
  const colorClasses = {
    blue: 'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400',
    emerald: 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400',
    amber: 'bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-400',
    purple: 'bg-purple-50 dark:bg-purple-900/20 text-purple-600 dark:text-purple-400',
  };

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-[var(--color-text-secondary)]">{title}</p>
          <p className="text-2xl font-bold text-[var(--color-text-primary)] mt-1">{value.toLocaleString()}</p>
        </div>
        <div className={`p-3 rounded-lg ${colorClasses[color as keyof typeof colorClasses]}`}>
          <span className="text-2xl">{icon}</span>
        </div>
      </div>
    </div>
  );
}
