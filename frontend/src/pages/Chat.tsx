import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../api';
import { Citation, StreamEvent } from '../types';
import { useAuth } from '../hooks/useAuth';
import Sidebar from '../components/Sidebar';
import Header from '../components/Header';
import EmptyState from '../components/ui/EmptyState';
import { Skeleton } from '../components/ui/Skeleton';
import { useToast } from '../components/ui/Toast';

export default function ChatPage() {
  const { conversationId } = useParams<{ conversationId?: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState<Array<{ role: string; content: string; citations?: Citation[]; metadata?: any }>>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Array<{ id: string; title?: string | null; updated_at: string }>>([]);
  const [loadingConversations, setLoadingConversations] = useState(true);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const { addToast } = useToast();

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

  const startNewChat = () => {
    setMessages([]);
    setError(null);
    navigate('/chat');
  };

  return (
    <div className="flex h-screen bg-[var(--color-bg-primary)]">
      <Sidebar />

      <div className="flex-1 flex flex-col overflow-hidden">
        <Header title="Chat" subtitle="Ask questions about your documents" />

        <div className="flex-1 flex overflow-hidden">
          {/* Conversations List */}
          <div className="w-72 border-r border-[var(--color-border)] bg-[var(--color-bg-secondary)] overflow-y-auto scrollbar-thin hidden lg:block">
            <div className="p-4">
              <button
                onClick={startNewChat}
                className="btn-primary w-full mb-4"
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                New Chat
              </button>
              {loadingConversations ? (
                <div className="space-y-2">
                  <Skeleton className="h-12 rounded-lg" />
                  <Skeleton className="h-12 rounded-lg" />
                  <Skeleton className="h-12 rounded-lg" />
                </div>
              ) : (
                <div className="space-y-1">
                  {conversations.map((conv) => (
                    <a
                      key={conv.id}
                      href={`/chat/${conv.id}`}
                      className={`flex items-center gap-3 p-3 rounded-lg text-sm transition-all duration-200 ${
                        conversationId === conv.id
                          ? 'bg-[var(--color-accent)] text-white shadow-sm'
                          : 'text-[var(--color-text-primary)] hover:bg-[var(--color-bg-tertiary)]'
                      }`}
                    >
                      <svg className="h-4 w-4 flex-shrink-0 opacity-70" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                      </svg>
                      <div className="min-w-0">
                        <p className="font-medium truncate">{conv.title || 'Untitled'}</p>
                        <p className={`text-xs mt-0.5 ${conversationId === conv.id ? 'text-white/70' : 'text-[var(--color-text-tertiary)]'}`}>
                          {new Date(conv.updated_at).toLocaleDateString()}
                        </p>
                      </div>
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
                <div className="flex flex-col items-center justify-center h-full text-center max-w-2xl mx-auto">
                  <div className="w-20 h-20 rounded-2xl bg-[var(--color-accent-light)] flex items-center justify-center mb-6">
                    <svg className="h-10 w-10 text-[var(--color-accent)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                    </svg>
                  </div>
                  <h2 className="text-2xl font-bold text-[var(--color-text-primary)] mb-3">Start a conversation</h2>
                  <p className="text-[var(--color-text-secondary)] max-w-md mb-8">
                    Ask questions about your uploaded documents. I'll search through them and provide answers with verifiable citations.
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-lg">
                    {[
                      'What are the key findings?',
                      'Summarize the main points',
                      'Explain the methodology',
                      'What are the conclusions?',
                    ].map((suggestion, i) => (
                      <button
                        key={i}
                        onClick={() => setQuery(suggestion)}
                        className="p-3 text-sm text-left rounded-lg border border-[var(--color-border)] hover:border-[var(--color-accent)] hover:bg-[var(--color-accent-light)] transition-all duration-200 text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]"
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {isStreaming && messages.length === 0 && (
                <div className="flex flex-col items-center justify-center h-full">
                  <div className="relative">
                    <div className="animate-spin rounded-full h-12 w-12 border-2 border-[var(--color-accent)] border-t-transparent"></div>
                    <div className="absolute inset-0 flex items-center justify-center">
                      <div className="h-3 w-3 rounded-full bg-[var(--color-accent)]"></div>
                    </div>
                  </div>
                  <p className="text-[var(--color-text-secondary)] mt-4">Thinking...</p>
                </div>
              )}

              <div className="max-w-3xl mx-auto space-y-6">
                {messages.map((msg, i) => (
                  <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-in`}>
                    <div className={`max-w-[85%] ${msg.role === 'user' ? 'order-2' : 'order-1'}`}>
                      <div className={`rounded-2xl px-5 py-3 ${
                        msg.role === 'user'
                          ? 'bg-[var(--color-accent)] text-white rounded-br-md shadow-sm'
                          : 'bg-[var(--color-bg-secondary)] text-[var(--color-text-primary)] rounded-bl-md border border-[var(--color-border)]'
                      }`}>
                        {msg.role === 'assistant' && (
                          <div className="flex items-center gap-2 mb-2">
                            <div className="h-6 w-6 rounded-full bg-[var(--color-accent)] flex items-center justify-center text-white text-xs font-medium">
                              AI
                            </div>
                            <span className="text-xs font-medium text-[var(--color-text-secondary)]">Assistant</span>
                          </div>
                        )}
                        <div className="whitespace-pre-wrap text-sm leading-relaxed">{msg.content || '\u00a0'}</div>

                        {msg.citations && msg.citations.length > 0 && (
                          <div className="mt-3 pt-3 border-t border-[var(--color-border)] space-y-2">
                            <p className="text-xs font-medium text-[var(--color-text-secondary)]">Sources:</p>
                            {msg.citations.map((c: Citation, j: number) => (
                              <div key={j} className="text-xs bg-[var(--color-bg-primary)] rounded-lg p-3 border border-[var(--color-border)] hover:border-[var(--color-accent)] transition-colors duration-200">
                                <div className="flex items-center justify-between mb-1">
                                  <span className="font-medium text-[var(--color-text-primary)]">
                                    [{j + 1}] {c.doc_filename}
                                  </span>
                                  <span className="text-[var(--color-text-tertiary)]">
                                    Page {c.page_number}
                                  </span>
                                </div>
                                <p className="mt-1 text-[var(--color-text-secondary)] line-clamp-2">
                                  {c.label}
                                </p>
                                <div className="mt-2 flex items-center gap-3">
                                  <span className="text-xs text-[var(--color-text-tertiary)]">
                                    Score: {(c.score * 100).toFixed(0)}%
                                  </span>
                                  {c.verified ? (
                                    <span className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">✓ Verified</span>
                                  ) : (
                                    <span className="text-xs text-amber-600 dark:text-amber-400 font-medium">⚠ Unverified</span>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>

                      {msg.metadata && (
                        <div className="mt-1.5 px-2 flex items-center gap-3 text-xs text-[var(--color-text-tertiary)]">
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
              <div className="px-6 py-3 bg-[var(--color-error-light)] border-t border-[var(--color-error)] text-[var(--color-error)] text-sm">
                <div className="flex items-center gap-2">
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  {error}
                </div>
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
                      className="input resize-none pr-12"
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
                        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" />
                        </svg>
                        Stop
                      </button>
                    ) : (
                      <>
                        <button
                          onClick={retryLast}
                          disabled={messages.length === 0}
                          className="btn-ghost px-4 py-2 disabled:opacity-50"
                          title="Retry last message"
                        >
                          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                          </svg>
                        </button>
                        <button
                          onClick={handleSend}
                          disabled={isStreaming || !query.trim()}
                          className="btn-primary px-6 py-2 disabled:opacity-50"
                        >
                          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                          </svg>
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
