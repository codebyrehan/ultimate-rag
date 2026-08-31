import { useState, useEffect } from 'react';
import api from '../api';
import { DocumentResponse, ConversationResponse, JobResponse } from '../types';
import { useChat } from '../hooks/useChat';

export default function DashboardPage() {
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
      setDocuments(docsRes.data);
      setConversations(convRes.data);
      setJobs(jobsRes.data);
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
    switch (status) {
      case 'indexed':
        return 'bg-green-100 text-green-800';
      case 'processing':
        return 'bg-yellow-100 text-yellow-800';
      case 'failed':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
          <h1 className="text-xl font-bold">Ultimate RAG Platform</h1>
          <nav>
            <a href="/chat" className="text-blue-600 hover:text-blue-800 ml-4">Chat</a>
            <a href="/conversations" className="text-blue-600 hover:text-blue-800 ml-4">Conversations</a>
            <a href="/settings" className="text-blue-600 hover:text-blue-800 ml-4">Settings</a>
            <button
              onClick={() => {
                localStorage.removeItem('access_token');
                localStorage.removeItem('tenant_name');
                window.location.href = '/login';
              }}
              className="text-gray-600 hover:text-gray-800 ml-4"
            >
              Logout
            </button>
          </nav>
        </div>
      </header>

      <main className="max-w-7xl mx-auto py-6 px-4">
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Documents</h2>
          <label className="bg-blue-600 text-white px-4 py-2 rounded cursor-pointer hover:bg-blue-700">
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
        {uploadError && <div className="mb-4 p-3 bg-red-100 text-red-800 rounded">{uploadError}</div>}

        {loading ? (
          <p className="text-gray-500">Loading...</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {documents.map((doc) => (
              <div key={doc.id} className="bg-white rounded-lg shadow p-4">
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="font-medium text-sm">{doc.original_filename || doc.filename}</h3>
                    <p className="text-xs text-gray-500 mt-1">{doc.page_count} pages</p>
                  </div>
                  <span className={`text-xs px-2 py-1 rounded ${getStatusColor(doc.status)}`}>
                    {doc.status}
                  </span>
                </div>
                <div className="mt-2 text-xs text-gray-500">
                  SHA: {doc.sha256.slice(0, 12)}...
                </div>
                <a
                  href={`/documents/${doc.id}`}
                  className="text-xs text-blue-600 hover:underline mt-2 block"
                >
                  View details →
                </a>
              </div>
            ))}
            {documents.length === 0 && <p className="text-gray-400">No documents uploaded yet.</p>}
          </div>
        )}

        <h2 className="text-lg font-semibold mt-8 mb-4">Conversations</h2>
        {conversations.length === 0 ? (
          <p className="text-gray-400">No conversations yet. Start chatting!</p>
        ) : (
          <div className="space-y-2">
            {conversations.slice(0, 10).map((conv) => (
              <a
                key={conv.id}
                href={`/chat/${conv.id}`}
                className="block p-3 bg-white rounded hover:bg-gray-50"
              >
                <span className="font-medium text-sm">{conv.title || conv.id.slice(0, 12)}</span>
                <span className="text-xs text-gray-500 ml-2">
                  {new Date(conv.updated_at).toLocaleString()}
                </span>
              </a>
            ))}
          </div>
        )}

        <h2 className="text-lg font-semibold mt-8 mb-4">Recent Jobs</h2>
        {jobs.length === 0 ? (
          <p className="text-gray-400">No jobs.</p>
        ) : (
          <div className="space-y-2">
            {jobs.slice(0, 10).map((job) => (
              <div key={job.id} className="p-3 bg-white rounded text-sm">
                <span className={`font-medium ${
                  job.status === 'completed' ? 'text-green-600' :
                  job.status === 'failed' ? 'text-red-600' : 'text-yellow-600'
                }`}>{job.status}</span>
                <span className="text-gray-500 ml-2">{job.kind}</span>
                {job.error && <span className="text-red-500 block mt-1">Error: {job.error}</span>}
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
