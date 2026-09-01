import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../api';
import { Citation, StreamEvent } from '../types';
import { useAuth } from '../hooks/useAuth';
import Sidebar from '../components/Sidebar';
import Header from '../components/Header';

export default function ChatPage() {
  const { conversationId } = useParams<{ conversationId?: string }>();
  const navigate = useNavigate();
  const { logout } = useAuth();
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState<Array<{ role: string; content: string; citations?: Citation[]; metadata?: any }>>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Array<{ id: string; title?: string | null; updated_at: string }>>([]);
  const [loadingConversations, setLoadingConversations] = useState(true);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isStreaming]);

  useEffect(() => {
    loadConversations();
    if (conversationId) {
      loadConversation(conversationId);
    }
  }, [conversationId]);

  async function loadConversations() {
    try {
      const res = await api.get('/conversations/');
      setConversations(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingConversations(false);
    }
  }

  async function loadConversation(id: string) {
    try {
      const res = await api.get(`/conversations/${id}`);
      const conv = res.data;
      setMessages(conv.messages.map((m: any) => ({
        role: m.role,
        content: m.content,
        citations: [],
        metadata: {},
      })));
    } catch (err) {
      console.error(err);
    }
  }

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isStreaming) return;

    setMessages((prev) => [...prev, { role: 'user', content: text }]);
    setQuery('');
    setError(null);
    setIsStreaming(true);

    try {
      const response = await api.post('/chat/stream', { query: text, conversation_id: conversationId || null }, {
        responseType: 'stream',
        signal: abortControllerRef.current?.signal,
      });

      const reader = response.data.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let assistantContent = '';
      let citations: Citation[] = [];
      let metadata: any = {};

      const processStream = async () => {
        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';
            for (const line of lines) {
              const trimmed = line.trim();
              if (!trimmed) continue;
              try {
                const event: StreamEvent = JSON.parse(trimmed);
                if (event.type === 'token' && event.data) {
                  assistantContent += event.data;
                  setMessages((prev) => {
                    const last = prev[prev.length - 1];
                    if (last && last.role === 'assistant') {
                      return [...prev.slice(0, -1), { ...last, content: assistantContent }];
                    }
                    return [...prev, { role: 'assistant', content: assistantContent, citations, metadata }];
                  });
                } else if (event.type === 'done') {
                  citations = event.citations || [];
                  metadata = { confidence: event.confidence, model: event.model, query_id: event.query_id, conversation_id: event.conversation_id };
                  setMessages((prev) => {
                    const last = prev[prev.length - 1];
                    if (last && last.role === 'assistant') {
                      return [...prev.slice(0, -1), { ...last, citations, metadata }];
                    }
                    return prev;
                  });
                  if (event.conversation_id && !conversationId) {
                    navigate(`/chat/${event.conversation_id}`, { replace: true });
                  }
                }
              } catch {}
            }
          }
        } catch (e) {
          if ((e as any).name !== 'AbortError') {
            setError('Streaming error');
          }
        } finally {
          setIsStreaming(false);
          abortControllerRef.current = null;
        }
      };

      abortControllerRef.current = new AbortController();
      processStream();
    } catch (err: any) {
      if (err.name !== 'CanceledError') {
        setError(err.response?.data?.detail || 'Request failed');
        setMessages((prev) => prev.filter((m) => m.role !== 'assistant'));
      }
      setIsStreaming(false);
    }
  }, [conversationId, isStreaming, navigate]);

  const handleSend = async () => {
    await sendMessage(query);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const stopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };

  const copyToClipboard = async (text: string, id: string) => {
    await navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const retryLast = () => {
    const lastUserMessage = [...messages].reverse().find((m) => m.role === 'user');
    if (lastUserMessage) {
      setMessages((prev) => prev.filter((m) => m.role !== 'assistant'));
      sendMessage(lastUserMessage.content);
    }
  };

  return (
    <div className="flex h-screen bg-[var(--color-bg-primary)]">
      <Sidebar />

      <div className="flex-1 flex flex-col overflow-hidden">
        <Header title="Chat" subtitle="Ask questions about your documents" />

        <div className="flex-1 flex overflow-hidden">
          {/* Conversations List */}
          <div className="w-64 border-r border-[var(--color-border)] bg-[var(--color-bg-secondary)] overflow-y-auto scrollbar-thin hidden md:block">
            <div className="p-4">
              <button
                onClick={() => {
                  setMessages([]);
                  navigate('/chat');
                }}
                className="btn-primary w-full mb-4"
              >
                New Chat
              </button>
              {loadingConversations ? (
                <p className="text-sm text-[var(--color-text-tertiary)]">Loading...</p>
              ) : (
                <div className="space-y-2">
                  {conversations.map((conv) => (
                    <a
                      key={conv.id}
                      href={`/chat/${conv.id}`}
                      className={`block p-3 rounded-lg text-sm transition-colors duration-200 ${
                        conversationId === conv.id
                          ? 'bg-[var(--color-accent)] text-white'
                          : 'hover:bg-[var(--color-bg-tertiary)] text-[var(--color-text-primary)]'
                      }`}
                    >
                      <p className="font-medium truncate">{conv.title || 'Untitled'}</p>
                      <p className="text-xs opacity-70 mt-1">
                        {new Date(conv.updated_at).toLocaleDateString()}
                      </p>
                    </a>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Chat Area */}
          <div className="flex-1 flex flex-col">
            <div className="flex-1 overflow-y-auto p-6 scrollbar-thin">
              {messages.length === 0 && !isStreaming && (
                <div className="flex flex-col items-center justify-center h-full text-center">
                  <div className="w-16 h-16 bg-[var(--color-accent)] rounded-full flex items-center justify-center mb-4">
                    <span className="text-2xl text-white">💬</span>
                  </div>
                  <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-2">Start a conversation</h2>
                  <p className="text-[var(--color-text-secondary)] max-w-md">
                    Ask questions about your uploaded documents. I'll search through them and provide answers with citations.
                  </p>
                </div>
              )}

              {isStreaming && messages.length === 0 && (
                <div className="flex flex-col items-center justify-center h-full">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--color-accent)] mb-4"></div>
                  <p className="text-[var(--color-text-secondary)]">Thinking...</p>
                </div>
              )}

              <div className="max-w-3xl mx-auto space-y-6">
                {messages.map((msg, i) => (
                  <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[85%] ${msg.role === 'user' ? 'order-2' : 'order-1'}`}>
                      <div className={`rounded-2xl px-5 py-3 ${
                        msg.role === 'user'
                          ? 'bg-[var(--color-accent)] text-white rounded-br-md'
                          : 'bg-[var(--color-bg-secondary)] text-[var(--color-text-primary)] rounded-bl-md border border-[var(--color-border)]'
                      }`}>
                        <div className="whitespace-pre-wrap text-sm leading-relaxed">{msg.content || '\u00a0'}</div>

                        {msg.citations && msg.citations.length > 0 && (
                          <div className="mt-3 pt-3 border-t border-[var(--color-border)] space-y-2">
                            <p className="text-xs font-medium opacity-70">Sources:</p>
                            {msg.citations.map((c: Citation, j: number) => (
                              <div key={j} className="text-xs bg-[var(--color-bg-primary)] rounded-lg p-3 border border-[var(--color-border)]">
                                <div className="flex items-center justify-between">
                                  <span className="font-medium">
                                    [{j + 1}] {c.doc_filename}
                                  </span>
                                  <span className="text-[var(--color-text-tertiary)]">
                                    Page {c.page_number}
                                  </span>
                                </div>
                                <p className="mt-1 text-[var(--color-text-secondary)] line-clamp-2">
                                  {c.label}
                                </p>
                                <div className="mt-2 flex items-center gap-2">
                                  <span className="text-xs opacity-70">
                                    Score: {(c.score * 100).toFixed(0)}%
                                  </span>
                                  {c.verified ? (
                                    <span className="text-xs text-green-600 dark:text-green-400">✓ Verified</span>
                                  ) : (
                                    <span className="text-xs text-amber-600 dark:text-amber-400">⚠ Unverified</span>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>

                      {msg.metadata && (
                        <div className="mt-1 px-2 flex items-center gap-3 text-xs text-[var(--color-text-tertiary)]">
                          {msg.metadata.confidence && (
                            <span>Confidence: {Math.round(msg.metadata.confidence * 100)}%</span>
                          )}
                          {msg.metadata.model && <span>Model: {msg.metadata.model}</span>}
                          <button
                            onClick={() => copyToClipboard(msg.content, `msg-${i}`)}
                            className="hover:text-[var(--color-accent)] transition-colors duration-200"
                          >
                            {copiedId === `msg-${i}` ? 'Copied!' : 'Copy'}
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>
            </div>

            {error && (
              <div className="px-6 py-3 bg-red-50 dark:bg-red-900/20 border-t border-red-200 dark:border-red-800 text-red-800 dark:text-red-200 text-sm">
                {error}
              </div>
            )}

            <div className="p-4 bg-[var(--color-bg-primary)] border-t border-[var(--color-border)]">
              <div className="max-w-3xl mx-auto">
                <div className="flex items-end gap-3">
                  <div className="flex-1 relative">
                    <textarea
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      onKeyDown={handleKeyPress}
                      placeholder="Ask about your documents..."
                      disabled={isStreaming}
                      className="input-field resize-none pr-12"
                      rows={1}
                      style={{ minHeight: '44px' }}
                    />
                  </div>
                  <div className="flex gap-2">
                    {isStreaming ? (
                      <button
                        onClick={stopGeneration}
                        className="btn-secondary px-4 py-2"
                      >
                        Stop
                      </button>
                    ) : (
                      <>
                        <button
                          onClick={retryLast}
                          disabled={messages.length === 0}
                          className="btn-secondary px-4 py-2 disabled:opacity-50"
                        >
                          Retry
                        </button>
                        <button
                          onClick={handleSend}
                          disabled={isStreaming || !query.trim()}
                          className="btn-primary px-6 py-2 disabled:opacity-50"
                        >
                          Send
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
