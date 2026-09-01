import { useState, useEffect } from 'react';
import api from '../api';
import { ConversationResponse, MessageInfo } from '../types';
import Header from '../components/Header';
import Sidebar from '../components/Sidebar';
import EmptyState from '../components/ui/EmptyState';
import { SkeletonCard } from '../components/ui/Skeleton';

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
        <div className="flex-1 flex flex-col overflow-hidden">
          <Header title="Conversations" subtitle="Loading..." />
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
        <Header title="Conversations" subtitle={`${conversations.length} conversations`} />

        <main className="flex-1 overflow-y-auto p-6 scrollbar-thin">
          {conversations.length === 0 ? (
            <div className="card p-12">
              <EmptyState
                icon="💬"
                title="No conversations yet"
                description="Start chatting with your documents to see conversations here."
                action={{ label: 'Start New Chat', onClick: () => window.location.href = '/chat' }}
              />
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {conversations.map((conv) => (
                <a
                  key={conv.id}
                  href={`/chat/${conv.id}`}
                  className="card p-6 hover:shadow-lg transition-all duration-200 group"
                >
                  <div className="flex items-start justify-between mb-3">
                    <h3 className="font-semibold text-[var(--color-text-primary)] line-clamp-1 group-hover:text-[var(--color-accent)] transition-colors duration-200">
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
                          className={`text-sm p-2.5 rounded-lg ${
                            m.role === 'user'
                              ? 'bg-[var(--color-accent)] text-white'
                              : 'bg-[var(--color-bg-secondary)] text-[var(--color-text-secondary)] border border-[var(--color-border)]'
                          }`}
                        >
                          <p className="line-clamp-2">{m.content.slice(0, 100)}{m.content.length > 100 ? '...' : ''}</p>
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
