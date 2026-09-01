import { useState, useEffect, useCallback } from 'react';
import api from '../api';
import { DocumentResponse, ConversationResponse, JobResponse } from '../types';
import Header from '../components/Header';
import Sidebar from '../components/Sidebar';
import EmptyState from '../components/ui/EmptyState';
import { SkeletonCard, SkeletonTable } from '../components/ui/Skeleton';
import { useToast } from '../components/ui/Toast';

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
  const [dragOver, setDragOver] = useState(false);
  const { addToast } = useToast();

  const fetchData = useCallback(async () => {
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
      setDocuments(docs.slice(0, 5));
      setConversations(convRes.data.slice(0, 5));
      setJobs(jobsRes.data.slice(0, 5));
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

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
      await fetchData();
    } catch (err: any) {
      addToast('error', err.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
      setDragOver(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    handleUpload(e.dataTransfer.files);
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'indexed': return 'badge-success';
      case 'processing': return 'badge-warning';
      case 'failed': return 'badge-error';
      default: return 'badge-neutral';
    }
  };

  if (loading) {
    return (
      <div className="flex h-screen bg-[var(--color-bg-primary)]">
        <Sidebar />
        <div className="flex-1 flex flex-col overflow-hidden">
          <Header title="Dashboard" subtitle="Loading..." />
          <main className="flex-1 overflow-y-auto p-6 scrollbar-thin">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
              {[1, 2, 3, 4].map(i => (
                <div key={i} className="card p-6">
                  <div className="skeleton h-4 w-24 rounded mb-3" />
                  <div className="skeleton h-8 w-16 rounded mb-4" />
                  <div className="skeleton h-10 w-10 rounded-lg" />
                </div>
              ))}
            </div>
            <SkeletonCard />
            <SkeletonCard />
          </main>
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
          {/* Stats Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <StatCard title="Documents" value={stats.documents} subtitle="Total uploaded" icon="📄" color="indigo" />
            <StatCard title="Indexed Chunks" value={stats.chunks} subtitle="Ready for search" icon="🧩" color="emerald" />
            <StatCard title="Processing Jobs" value={stats.jobs} subtitle="Active tasks" icon="⚙️" color="amber" />
            <StatCard title="Conversations" value={stats.conversations} subtitle="Chat sessions" icon="💬" color="violet" />
          </div>

          {/* Upload Section */}
          <div className="card p-6 mb-8">
            <h3 className="text-lg font-semibold text-[var(--color-text-primary)] mb-4">Upload Document</h3>
            <label
              className={`flex flex-col items-center justify-center w-full h-32 border-2 border-dashed rounded-xl cursor-pointer transition-all duration-200 ${
                dragOver
                  ? 'border-[var(--color-accent)] bg-[var(--color-accent-light)]'
                  : 'border-[var(--color-border)] hover:border-[var(--color-accent)] hover:bg-[var(--color-bg-secondary)]'
              }`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              <div className="flex flex-col items-center justify-center pt-5 pb-6">
                <svg className="w-8 h-8 mb-2 text-[var(--color-text-tertiary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
                <p className="text-sm text-[var(--color-text-secondary)]">
                  {uploading ? 'Uploading...' : dragOver ? 'Drop files here' : 'Click to upload or drag and drop PDF'}
                </p>
              </div>
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

          {/* Recent Documents */}
          <div className="card mb-8">
            <div className="card-header flex items-center justify-between">
              <h3 className="text-lg font-semibold">Recent Documents</h3>
              <a href="/documents" className="text-sm text-[var(--color-accent)] hover:text-[var(--color-accent-hover)] font-medium">
                View all
              </a>
            </div>
            {documents.length === 0 ? (
              <div className="card-body">
                <EmptyState
                  icon="📄"
                  title="No documents yet"
                  description="Upload your first PDF to get started with document intelligence."
                  action={{ label: 'Upload Document', onClick: () => {} }}
                />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-[var(--color-border)]">
                  <thead>
                    <tr className="bg-[var(--color-bg-secondary)]">
                      <th className="px-6 py-3 text-left text-xs font-semibold text-[var(--color-text-secondary)] uppercase tracking-wider">Name</th>
                      <th className="px-6 py-3 text-left text-xs font-semibold text-[var(--color-text-secondary)] uppercase tracking-wider">Status</th>
                      <th className="px-6 py-3 text-left text-xs font-semibold text-[var(--color-text-secondary)] uppercase tracking-wider">Pages</th>
                      <th className="px-6 py-3 text-left text-xs font-semibold text-[var(--color-text-secondary)] uppercase tracking-wider">Chunks</th>
                      <th className="px-6 py-3 text-left text-xs font-semibold text-[var(--color-text-secondary)] uppercase tracking-wider">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--color-border)]">
                    {documents.map((doc) => (
                      <tr key={doc.id} className="hover:bg-[var(--color-bg-secondary)] transition-colors duration-150">
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-3">
                            <div className="h-10 w-10 rounded-lg bg-red-50 dark:bg-red-900/20 flex items-center justify-center text-red-600 dark:text-red-400">
                              <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clipRule="evenodd" />
                              </svg>
                            </div>
                            <div>
                              <p className="text-sm font-medium text-[var(--color-text-primary)] line-clamp-1">{doc.original_filename || doc.filename}</p>
                              <p className="text-xs text-[var(--color-text-tertiary)]">v{doc.version}</p>
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <span className={`badge ${getStatusColor(doc.status)}`}>{doc.status}</span>
                        </td>
                        <td className="px-6 py-4 text-sm text-[var(--color-text-secondary)]">{doc.page_count}</td>
                        <td className="px-6 py-4 text-sm text-[var(--color-text-secondary)]">{doc.chunks.length}</td>
                        <td className="px-6 py-4">
                          <a href={`/documents/${doc.id}`} className="text-sm text-[var(--color-accent)] hover:text-[var(--color-accent-hover)] font-medium">
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

          {/* Recent Conversations & Jobs Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Recent Conversations */}
            <div className="card">
              <div className="card-header flex items-center justify-between">
                <h3 className="text-lg font-semibold">Recent Conversations</h3>
                <a href="/conversations" className="text-sm text-[var(--color-accent)] hover:text-[var(--color-accent-hover)] font-medium">
                  View all
                </a>
              </div>
              {conversations.length === 0 ? (
                <div className="card-body">
                  <EmptyState
                    icon="💬"
                    title="No conversations yet"
                    description="Start chatting with your documents to see conversations here."
                    action={{ label: 'Start Chat', onClick: () => window.location.href = '/chat' }}
                  />
                </div>
              ) : (
                <div className="divide-y divide-[var(--color-border)]">
                  {conversations.map((conv) => (
                    <a
                      key={conv.id}
                      href={`/chat/${conv.id}`}
                      className="flex items-center justify-between p-4 hover:bg-[var(--color-bg-secondary)] transition-colors duration-200"
                    >
                      <div className="flex items-center gap-3">
                        <div className="h-10 w-10 rounded-full bg-[var(--color-accent-light)] flex items-center justify-center text-[var(--color-accent)]">
                          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                          </svg>
                        </div>
                        <div>
                          <p className="font-medium text-[var(--color-text-primary)]">{conv.title || 'Untitled Conversation'}</p>
                          <p className="text-sm text-[var(--color-text-secondary)]">{conv.messages.length} messages</p>
                        </div>
                      </div>
                      <span className="text-xs text-[var(--color-text-tertiary)]">
                        {new Date(conv.updated_at).toLocaleDateString()}
                      </span>
                    </a>
                  ))}
                </div>
              )}
            </div>

            {/* Processing Jobs */}
            <div className="card">
              <div className="card-header flex items-center justify-between">
                <h3 className="text-lg font-semibold">Processing Jobs</h3>
                <span className="badge badge-neutral">{jobs.length} active</span>
              </div>
              {jobs.length === 0 ? (
                <div className="card-body">
                  <EmptyState
                    icon="⚙️"
                    title="No active jobs"
                    description="Uploaded documents will appear here during processing."
                  />
                </div>
              ) : (
                <div className="divide-y divide-[var(--color-border)]">
                  {jobs.map((job) => (
                    <div key={job.id} className="flex items-center justify-between p-4 hover:bg-[var(--color-bg-secondary)] transition-colors duration-150">
                      <div className="flex items-center gap-3">
                        <div className={`h-10 w-10 rounded-full flex items-center justify-center ${
                          job.status === 'completed' ? 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600' :
                          job.status === 'failed' ? 'bg-red-50 dark:bg-red-900/20 text-red-600' :
                          'bg-amber-50 dark:bg-amber-900/20 text-amber-600'
                        }`}>
                          <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            {job.status === 'completed' ? (
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            ) : job.status === 'failed' ? (
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            ) : (
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                            )}
                          </svg>
                        </div>
                        <div>
                          <p className="font-medium text-[var(--color-text-primary)] capitalize">{job.kind}</p>
                          <p className="text-sm text-[var(--color-text-secondary)]">ID: {job.id.slice(0, 12)}...</p>
                          {job.error && <p className="text-sm text-red-600 mt-1 line-clamp-1">{job.error}</p>}
                        </div>
                      </div>
                      <span className={`badge ${getStatusColor(job.status)} capitalize`}>{job.status}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

function StatCard({ title, value, subtitle, icon, color }: { title: string; value: number; subtitle: string; icon: string; color: string }) {
  const colorClasses = {
    indigo: 'bg-indigo-50 dark:bg-indigo-900/20 text-indigo-600 dark:text-indigo-400',
    emerald: 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400',
    amber: 'bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-400',
    violet: 'bg-violet-50 dark:bg-violet-900/20 text-violet-600 dark:text-violet-400',
  };

  return (
    <div className="card p-6 hover:shadow-lg transition-all duration-200">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-[var(--color-text-secondary)]">{title}</p>
          <p className="text-3xl font-bold text-[var(--color-text-primary)] mt-1">{value.toLocaleString()}</p>
          <p className="text-xs text-[var(--color-text-tertiary)] mt-1">{subtitle}</p>
        </div>
        <div className={`h-12 w-12 rounded-xl flex items-center justify-center text-2xl ${colorClasses[color as keyof typeof colorClasses]}`}>
          {icon}
        </div>
      </div>
    </div>
  );
}
