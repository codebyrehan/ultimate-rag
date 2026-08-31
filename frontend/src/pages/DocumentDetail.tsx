import { useParams } from 'react-router-dom';
import { useEffect, useState } from 'react';
import api from '../api';
import { DocumentResponse } from '../types';
import PdfViewer from '../components/PdfViewer';

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

  if (loading) return <p className="p-4 text-gray-500">Loading...</p>;
  if (!doc) return <p className="p-4 text-gray-500">Document not found.</p>;

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow">
        <div className="max-w-4xl mx-auto px-4 py-3 flex justify-between items-center">
          <h1 className="text-lg font-bold">Document</h1>
          <a href="/" className="text-blue-600 hover:text-blue-800">
            ← Back
          </a>
        </div>
      </header>

      <main className="max-w-4xl mx-auto py-6 px-4">
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-bold">{doc.original_filename || doc.filename}</h2>
          <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="font-medium text-gray-500">Status:</span>{' '}
              <span
                className={
                  doc.status === 'indexed'
                    ? 'text-green-600'
                    : doc.status === 'failed'
                    ? 'text-red-600'
                    : 'text-yellow-600'
                }
              >
                {doc.status}
              </span>
            </div>
            <div>
              <span className="font-medium text-gray-500">Pages:</span> {doc.page_count}
            </div>
            <div>
              <span className="font-medium text-gray-500">Chunks:</span> {doc.chunks.length}
            </div>
            <div>
              <span className="font-medium text-gray-500">SHA-256:</span>{' '}
              <code className="text-xs">{doc.sha256}</code>
            </div>
            <div>
              <span className="font-medium text-gray-500">Version:</span> {doc.version}
            </div>
          </div>

          {doc.chunks.length > 0 && (
            <div className="mt-6">
              <h3 className="font-semibold mb-2">Chunks</h3>
              <div className="space-y-2 text-sm">
                {doc.chunks.map((chunk) => (
                  <div key={chunk.id} className="p-2 bg-gray-50 rounded">
                    <span className="font-medium">Chunk {chunk.id.slice(0, 8)}</span>
                    <span className="text-gray-500 ml-2">
                      Page {chunk.page_number}
                      {chunk.section && ` — ${chunk.section}`}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="mt-6">
            <h3 className="font-semibold mb-2">Document Preview</h3>
            <PdfViewer
              documentId={doc.id}
              filename={doc.original_filename || doc.filename}
              pageCount={doc.page_count}
            />
          </div>
        </div>
      </main>
    </div>
  );
}
