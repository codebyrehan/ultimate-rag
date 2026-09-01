import { useState, useEffect } from 'react';
import api from '../api';
import { ConversationResponse, MessageInfo } from '../types';
import Header from '../components/Header';
import Sidebar from '../components/Sidebar';

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
        <Header title="Conversations" subtitle={`${conversations.length} conversations`} />

        <main className="flex-1 overflow-y-auto p-6 scrollbar-thin">
          {conversations.length === 0 ? (
            <div className="card p-12 text-center">
              <div className="text-6xl mb-4">💬</div>
              <h3 className="text-lg font-semibold text-[var(--color-text-primary)] mb-2">No conversations yet</h3>
              <p className="text-[var(--color-text-secondary)] mb-6">
                Start chatting with your documents to see conversations here.
              </p>
              <a href="/chat" className="btn-primary">
                Start New Chat
              </a>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {conversations.map((conv) => (
                <a
                  key={conv.id}
                  href={`/chat/${conv.id}`}
                  className="card p-6 hover:shadow-md transition-shadow duration-200"
                >
                  <div className="flex items-start justify-between mb-3">
                    <h3 className="font-semibold text-[var(--color-text-primary)] line-clamp-1">
                      {conv.title || 'Untitled Conversation'}
                    </h3>
                    <span className="text-xs text-[var(--color-text-tertiary)] whitespace-nowrap ml-2">
                      {new Date(conv.updated_at).toLocaleDateString()}
                    </span>
                  </div>
                  <p className="text-sm text-[var(--color-text-secondary)] mb-4">
                    {conv.messages.length} messages
                  </p>
                  {conv.messages.length > 0 && (
                    <div className="space-y-2">
                      {conv.messages.slice(0, 3).map((m: MessageInfo) => (
                        <div
                          key={m.id}
                          className={`text-sm p-2 rounded ${
                            m.role === 'user'
                              ? 'bg-[var(--color-accent)] text-white'
                              : 'bg-[var(--color-bg-secondary)] text-[var(--color-text-secondary)]'
                          }`}
                        >
                          {m.content.slice(0, 80)}{m.content.length > 80 ? '...' : ''}
                        </div>
                      ))}
                    </div>
                  )}
                </a>
              ))}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
