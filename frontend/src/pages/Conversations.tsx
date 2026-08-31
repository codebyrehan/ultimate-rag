import { useState, useEffect } from 'react';
import api from '../api';
import { ConversationResponse, MessageInfo } from '../types';

export default function ConversationsPage() {
  const [conversations, setConversations] = useState<ConversationResponse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get('/conversations/')
      .then((res) => setConversations(res.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="p-4 text-gray-500">Loading...</p>;

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow">
        <div className="max-w-4xl mx-auto px-4 py-3 flex justify-between items-center">
          <h1 className="text-lg font-bold">Conversations</h1>
          <nav>
            <a href="/" className="text-blue-600 hover:text-blue-800 mr-4">Home</a>
            <a href="/chat" className="text-blue-600 hover:text-blue-800 mr-4">New Chat</a>
            <button
              onClick={() => {
                localStorage.removeItem('access_token');
                window.location.href = '/login';
              }}
              className="text-gray-600 hover:text-gray-800"
            >
              Logout
            </button>
          </nav>
        </div>
      </header>

      <main className="max-w-4xl mx-auto py-6 px-4">
        {conversations.length === 0 ? (
          <p className="text-gray-400">No conversations yet.</p>
        ) : (
          <div className="space-y-4">
            {conversations.map((conv) => (
              <div key={conv.id} className="bg-white rounded-lg shadow p-4">
                <div className="flex justify-between">
                  <span className="font-medium">{conv.title || conv.id.slice(0, 12)}</span>
                  <span className="text-xs text-gray-500">
                    {new Date(conv.updated_at).toLocaleString()}
                  </span>
                </div>
                <div className="mt-2 text-xs text-gray-500">
                  {conv.messages.length} messages
                </div>
                {conv.messages.length > 0 && (
                  <div className="mt-2 max-h-32 overflow-y-auto text-sm">
                    {conv.messages.map((m: MessageInfo) => (
                      <div
                        key={m.id}
                        className={`${m.role === 'user' ? 'text-blue-600' : 'text-gray-700'} mb-1`}
                      >
                        <span className="font-medium">
                          {m.role === 'user' ? 'You' : 'RAG'}
                        </span>
                        : {m.content.slice(0, 100)}
                        {m.content.length > 100 && '...'}
                      </div>
                    ))}
                  </div>
                )}
                <a
                  href={`/chat/${conv.id}`}
                  className="text-xs text-blue-600 hover:underline mt-2 block"
                >
                  Continue →
                </a>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
