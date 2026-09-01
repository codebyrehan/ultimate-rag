import { useState, useEffect } from 'react';
import api from '../api';
import Header from '../components/Header';
import Sidebar from '../components/Sidebar';

interface Settings {
  llm_provider: string;
  embedding_provider: string;
  vector_store_provider: string;
  reranker_provider: string;
  inline_worker: boolean;
  cache_enabled: boolean;
  claim_extraction_enabled: boolean;
  faithfulness_check_enabled: boolean;
  ocr_enabled: boolean;
  max_upload_size_mb: number;
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    fetchSettings();
  }, []);

  async function fetchSettings() {
    try {
      const res = await api.get('/ready');
      setSettings(res.data as Settings);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  const handleSave = async () => {
    if (!settings) return;
    setSaving(true);
    setMessage(null);
    try {
      await api.post('/settings', settings);
      setMessage('Settings saved successfully');
    } catch (err: any) {
      setMessage(err.response?.data?.detail || 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

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

  if (!settings) {
    return (
      <div className="flex h-screen bg-[var(--color-bg-primary)]">
        <Sidebar />
        <div className="flex-1 flex items-center justify-center">
          <p className="text-[var(--color-text-secondary)]">Failed to load settings.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-[var(--color-bg-primary)]">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header title="Settings" subtitle="Configure your RAG system" />

        <main className="flex-1 overflow-y-auto p-6 scrollbar-thin">
          <div className="max-w-3xl mx-auto space-y-6">
            {message && (
              <div className={`p-4 rounded-lg ${
                message.includes('Failed')
                  ? 'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-800 dark:text-red-200'
                  : 'bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 text-green-800 dark:text-green-200'
              }`}>
                {message}
              </div>
            )}

            {/* Model Configuration */}
            <div className="card p-6">
              <h3 className="text-lg font-semibold text-[var(--color-text-primary)] mb-4">Model Configuration</h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-[var(--color-text-secondary)] mb-1">
                    LLM Provider
                  </label>
                  <select
                    value={settings.llm_provider}
                    onChange={(e) => setSettings({ ...settings, llm_provider: e.target.value })}
                    className="input-field"
                  >
                    <option value="stub">Stub (Demo)</option>
                    <option value="ollama">Ollama (Local)</option>
                    <option value="openai">OpenAI</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-[var(--color-text-secondary)] mb-1">
                    Embedding Provider
                  </label>
                  <select
                    value={settings.embedding_provider}
                    onChange={(e) => setSettings({ ...settings, embedding_provider: e.target.value })}
                    className="input-field"
                  >
                    <option value="local">Local (Sentence Transformers)</option>
                    <option value="openai">OpenAI</option>
                    <option value="huggingface">HuggingFace</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-[var(--color-text-secondary)] mb-1">
                    Vector Store
                  </label>
                  <select
                    value={settings.vector_store_provider}
                    onChange={(e) => setSettings({ ...settings, vector_store_provider: e.target.value })}
                    className="input-field"
                  >
                    <option value="in_memory">In-Memory</option>
                    <option value="pgvector">PgVector</option>
                    <option value="qdrant">Qdrant</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-[var(--color-text-secondary)] mb-1">
                    Reranker Provider
                  </label>
                  <select
                    value={settings.reranker_provider}
                    onChange={(e) => setSettings({ ...settings, reranker_provider: e.target.value })}
                    className="input-field"
                  >
                    <option value="stub">Stub (Demo)</option>
                    <option value="cohere">Cohere</option>
                    <option value="local">Local</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Processing Options */}
            <div className="card p-6">
              <h3 className="text-lg font-semibold text-[var(--color-text-primary)] mb-4">Processing Options</h3>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-[var(--color-text-primary)]">Inline Worker</p>
                    <p className="text-sm text-[var(--color-text-secondary)]">Process jobs in-process instead of using a queue</p>
                  </div>
                  <button
                    onClick={() => setSettings({ ...settings, inline_worker: !settings.inline_worker })}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 ${
                      settings.inline_worker ? 'bg-[var(--color-accent)]' : 'bg-gray-200 dark:bg-gray-700'
                    }`}
                  >
                    <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform duration-200 ${
                      settings.inline_worker ? 'translate-x-6' : 'translate-x-1'
                    }`} />
                  </button>
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-[var(--color-text-primary)]">Cache Enabled</p>
                    <p className="text-sm text-[var(--color-text-secondary)]">Cache embeddings for faster retrieval</p>
                  </div>
                  <button
                    onClick={() => setSettings({ ...settings, cache_enabled: !settings.cache_enabled })}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 ${
                      settings.cache_enabled ? 'bg-[var(--color-accent)]' : 'bg-gray-200 dark:bg-gray-700'
                    }`}
                  >
                    <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform duration-200 ${
                      settings.cache_enabled ? 'translate-x-6' : 'translate-x-1'
                    }`} />
                  </button>
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-[var(--color-text-primary)]">OCR Enabled</p>
                    <p className="text-sm text-[var(--color-text-secondary)]">Enable optical character recognition for scanned PDFs</p>
                  </div>
                  <button
                    onClick={() => setSettings({ ...settings, ocr_enabled: !settings.ocr_enabled })}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 ${
                      settings.ocr_enabled ? 'bg-[var(--color-accent)]' : 'bg-gray-200 dark:bg-gray-700'
                    }`}
                  >
                    <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform duration-200 ${
                      settings.ocr_enabled ? 'translate-x-6' : 'translate-x-1'
                    }`} />
                  </button>
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-[var(--color-text-primary)]">Claim Extraction</p>
                    <p className="text-sm text-[var(--color-text-secondary)]">Extract verifiable claims from answers</p>
                  </div>
                  <button
                    onClick={() => setSettings({ ...settings, claim_extraction_enabled: !settings.claim_extraction_enabled })}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 ${
                      settings.claim_extraction_enabled ? 'bg-[var(--color-accent)]' : 'bg-gray-200 dark:bg-gray-700'
                    }`}
                  >
                    <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform duration-200 ${
                      settings.claim_extraction_enabled ? 'translate-x-6' : 'translate-x-1'
                    }`} />
                  </button>
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-[var(--color-text-primary)]">Faithfulness Check</p>
                    <p className="text-sm text-[var(--color-text-secondary)]">Verify answer faithfulness to source documents</p>
                  </div>
                  <button
                    onClick={() => setSettings({ ...settings, faithfulness_check_enabled: !settings.faithfulness_check_enabled })}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 ${
                      settings.faithfulness_check_enabled ? 'bg-[var(--color-accent)]' : 'bg-gray-200 dark:bg-gray-700'
                    }`}
                  >
                    <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform duration-200 ${
                      settings.faithfulness_check_enabled ? 'translate-x-6' : 'translate-x-1'
                    }`} />
                  </button>
                </div>
              </div>
            </div>

            {/* System Info */}
            <div className="card p-6">
              <h3 className="text-lg font-semibold text-[var(--color-text-primary)] mb-4">System Information</h3>
              <div className="space-y-3">
                <InfoRow label="Max Upload Size" value={`${settings.max_upload_size_mb} MB`} />
                <InfoRow label="Inline Worker" value={settings.inline_worker ? 'Enabled' : 'Disabled'} />
                <InfoRow label="Cache" value={settings.cache_enabled ? 'Enabled' : 'Disabled'} />
                <InfoRow label="OCR" value={settings.ocr_enabled ? 'Enabled' : 'Disabled'} />
              </div>
            </div>

            <div className="flex justify-end">
              <button
                onClick={handleSave}
                disabled={saving}
                className="btn-primary px-8 disabled:opacity-50"
              >
                {saving ? 'Saving...' : 'Save Settings'}
              </button>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between py-2 border-b border-[var(--color-border)] last:border-0">
      <span className="text-[var(--color-text-secondary)]">{label}</span>
      <span className="font-medium text-[var(--color-text-primary)]">{value}</span>
    </div>
  );
}
