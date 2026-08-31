import { useState, useCallback } from 'react';
import axios from 'axios';
import api from '../api';
import { ChatRequest, StreamEvent, Citation } from '../types';

interface UseChatResult {
  messages: Array<{ role: string; content: string; citations?: Citation[] }>;
  sendMessage: (query: string, conversationId?: string | null) => Promise<void>;
  isStreaming: boolean;
  error: string | null;
  answerMetadata: { confidence: number; model: string; citations: Citation[]; query_id: string } | null;
}

export function useChat(): UseChatResult {
  const [messages, setMessages] = useState<
    Array<{ role: string; content: string; citations?: Citation[] }>
  >([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [answerMetadata, setAnswerMetadata] = useState<null | {
    confidence: number;
    model: string;
    citations: Citation[];
    query_id: string;
  }>(null);

  const sendMessage = useCallback(
    async (query: string, conversationId?: string | null) => {
      setError(null);
      setAnswerMetadata(null);
      setMessages((prev) => [...prev, { role: 'user', content: query }]);
      setIsStreaming(true);

      try {
        const response = await api.post(
          '/chat/stream',
          {
            query,
            conversation_id: conversationId,
          } as ChatRequest,
          {
            responseType: 'stream',
          }
        );

        const reader = response.data.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

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
                    setMessages((prev) => {
                      const last = prev[prev.length - 1];
                      if (last && last.role === 'assistant') {
                        return [...prev.slice(0, -1), {
                          ...last,
                          content: last.content + event.data!,
                        }];
                      }
                      return [...prev, { role: 'assistant', content: event.data! }];
                    });
                  } else if (event.type === 'done') {
                    setAnswerMetadata({
                      confidence: event.confidence ?? 0,
                      model: event.model ?? '',
                      citations: event.citations ?? [],
                      query_id: event.query_id ?? '',
                    });
                  }
                } catch {}
              }
            }
          } catch (e) {
            setError('Streaming error');
          } finally {
            setIsStreaming(false);
          }
        };
        processStream().catch((e) => {
          setError('Streaming error');
          setIsStreaming(false);
        });
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Request failed');
        setMessages((prev) => prev.filter((m) => m.role !== 'assistant'));
        setIsStreaming(false);
      }
    },
    [],
  );

  return { messages, sendMessage, isStreaming, error, answerMetadata };
}
