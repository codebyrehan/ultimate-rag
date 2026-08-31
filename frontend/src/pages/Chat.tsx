import { useParams, useNavigate } from 'react-router-dom';
import { useChat } from '../hooks/useChat';
import { Citation } from '../types';
import { useAuth } from '../hooks/useAuth';
import { useState, useEffect, useRef } from 'react';
import api from '../api';
import { ConversationResponse } from '../types';

export default function ChatPage() {
  const { conversationId } = useParams<{ conversationId?: string }>();
  const navigate = useNavigate();
  const { logout } = useAuth();
  const { messages, sendMessage, isStreaming, error, answerMetadata } = useChat();
  const [query, setQuery] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isStreaming]);

  const handleSend = async () => {
    if (!query.trim()) return;
    await sendMessage(query, conversationId);
    setQuery('');
    if (!conversationId && answerMetadata) {
      navigate(`/chat`);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <header className="bg-white shadow">
        <div className="max-w-4xl mx-auto px-4 py-3 flex justify-between items-center">
          <h1 className="text-lg font-bold">Ultimate RAG Chat</h1>
          <nav>
            <a href="/" className="text-blue-600 hover:text-blue-800 mr-4">Home</a>
            <button
              onClick={logout}
              className="text-gray-600 hover:text-gray-800"
            >
              Logout
            </button>
          </nav>
        </div>
      </header>

      <main className="flex-1 overflow-y-auto max-w-4xl mx-auto w-full px-4 py-4">
        {messages.length === 0 && !isStreaming && (
          <p className="text-center text-gray-400 mt-8">
            Ask a question about your documents.
          </p>
        )}
        {isStreaming && messages.length === 0 && (
          <p className="text-center text-gray-400 mt-8">
            <span className="animate-pulse">Thinking...</span>
          </p>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`mb-4 ${msg.role === 'user' ? 'text-right' : 'text-left'}`}>
            <div
              className={`inline-block max-w-[80%] px-4 py-2 rounded-lg ${
                msg.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-white text-gray-900 shadow'
              }`}
            >
              <div className="whitespace-pre-wrap text-sm">{msg.content || '\u00a0'}</div>
              {msg.citations && msg.citations.length > 0 && (
                <div className="mt-2 pt-2 border-t border-gray-200 space-y-1">
                  {msg.citations.map((c: Citation, j: number) => (
                    <div key={j} className="text-xs text-gray-600">
                      <span
                        className={`font-medium mr-1 ${c.verified ? 'text-green-700' : 'text-amber-700'}`}
                      >
                        [{j + 1}]
                      </span>
                      {c.doc_filename} — Page {c.page_number}
                      {c.supported_fraction !== undefined && c.supported_fraction < 1 && (
                        <span className="text-yellow-600">⚠</span>
                      )}
                      {c.verified && <span className="text-green-600">✓</span>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

          {answerMetadata && (
            <div className="mb-4 p-3 bg-gray-100 rounded text-xs text-gray-600 flex justify-between items-center">
              <span>
                Confidence: {Math.round(answerMetadata.confidence * 100)}% · Model: {answerMetadata.model}
              </span>
              {answerMetadata.citations && answerMetadata.citations.length > 0 && (
                <span className="text-gray-500">
                  {answerMetadata.citations.filter((c: Citation) => c.verified).length}/{answerMetadata.citations.length} verified
                </span>
              )}
            </div>
          )}

        {error && <div className="p-3 bg-red-100 text-red-800 rounded">{error}</div>}
        <div ref={messagesEndRef} />
      </main>

      <footer className="bg-white border-t p-4">
        <div className="max-w-4xl mx-auto">
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyPress}
            placeholder="Ask about your documents..."
            disabled={isStreaming}
            className="w-full px-3 py-2 border rounded resize-none"
            rows={2}
          />
      <button
        onClick={handleSend}
        disabled={isStreaming || !query.trim()}
        className="mt-2 w-full bg-blue-600 text-white py-2 rounded hover:bg-blue-700 disabled:opacity-50 flex justify-center items-center"
      >
        {isStreaming ? (
          <>
            <span className="animate-spin mr-2 border-2 border-white border-t-transparent rounded-full w-4 h-4"></span>
            Thinking...
          </>
        ) : (
          'Send'
        )}
      </button>
        </div>
      </footer>
    </div>
  );
}
