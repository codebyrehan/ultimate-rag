import { useState, useEffect } from 'react';
import api from '../api';
import Header from '../components/Header';
import Sidebar from '../components/Sidebar';
import { Skeleton } from '../components/ui/Skeleton';
import { useToast } from '../components/ui/Toast';

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
  const { addToast } = useToast();

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
      addToast('success', 'Settings saved successfully');
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Failed to save settings';
      setMessage(msg);
      addToast('error', msg);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-screen bg-[var(--color-bg-primary)]">
        <Sidebar />
        <div className="flex-1 flex flex-col overflow-hidden">
          <Header title="Settings" subtitle="Loading..." />
          <main className="flex-1 overflow-y-auto p-6 scrollbar-thin">
            <div className="max-w-3xl mx-auto space-y-6">
              {[1, 2, 3].map(i => (
                <div key={i} className="card p-6 space-y-4">
                  <Skeleton className="h-6 w-48 rounded" />
                  <Skeleton className="h-10 w-full rounded-lg" />
                  <Skeleton className="h-10 w-full rounded-lg" />
                </div>
              ))}
            </div>
          </main>
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
              <div className={`p-4 rounded-lg border ${
                message.includes('Failed')
                  ? 'bg-[var(--color-error-light)] border-[var(--color-error)] text-[var(--color-error)]'
                  : 'bg-[var(--color-success-light)] border-[var(--color-success)] text-[var(--color-success)]'
              }`}>
                <div className="flex items-center gap-2">
                  <svg className="h-5 w-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    {message.includes('Failed') ? (
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    ) : (
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    )}
                  </svg>
                  <p className="text-sm font-medium">{message}</p>
                </div>
              </div>
            )}

            {/* Model Configuration */}
            <div className="card">
              <div className="card-header">
                <h3 className="text-lg font-semibold">Model Configuration</h3>
                <p className="text-sm text-[var(--color-text-secondary)] mt-1">Choose your AI providers and models</p>
              </div>
              <div className="card-body space-y-4">
                <div>
                  <label htmlFor="llm_provider" className="label">LLM Provider</label>
                  <select
                    id="llm_provider"
                    value={settings.llm_provider}
                    onChange={(e) => setSettings({ ...settings, llm_provider: e.target.value })}
                    className="input"
                  >
                    <option value="stub">Stub (Demo)</option>
                    <option value="ollama">Ollama (Local)</option>
                    <option value="openai">OpenAI</option>
                  </select>
                </div>

                <div>
                  <label htmlFor="embedding_provider" className="label">Embedding Provider</label>
                  <select
                    id="embedding_provider"
                    value={settings.embedding_provider}
                    onChange={(e) => setSettings({ ...settings, embedding_provider: e.target.value })}
                    className="input"
                  >
                    <option value="local">Local (Sentence Transformers)</option>
                    <option value="openai">OpenAI</option>
                    <option value="huggingface">HuggingFace</option>
                  </select>
                </div>

                <div>
                  <label htmlFor="vector_store_provider" className="label">Vector Store</label>
                  <select
                    id="vector_store_provider"
                    value={settings.vector_store_provider}
                    onChange={(e) => setSettings({ ...settings, vector_store_provider: e.target.value })}
                    className="input"
                  >
                    <option value="in_memory">In-Memory</option>
                    <option value="pgvector">PgVector</option>
                    <option value="qdrant">Qdrant</option>
                  </select>
                </div>

                <div>
                  <label htmlFor="reranker_provider" className="label">Reranker Provider</label>
                  <select
                    id="reranker_provider"
                    value={settings.reranker_provider}
                    onChange={(e) => setSettings({ ...settings, reranker_provider: e.target.value })}
                    className="input"
                  >
                    <option value="stub">Stub (Demo)</option>
                    <option value="cohere">Cohere</option>
                    <option value="local">Local</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Processing Options */}
            <div className="card">
              <div className="card-header">
                <h3 className="text-lg font-semibold">Processing Options</h3>
                <p className="text-sm text-[var(--color-text-secondary)] mt-1">Control how documents are processed</p>
              </div>
              <div className="card-body space-y-4">
                <ToggleSetting
                  label="Inline Worker"
                  description="Process jobs in-process instead of using a queue"
                  checked={settings.inline_worker}
                  onChange={(checked) => setSettings({ ...settings, inline_worker: checked })}
                />
                <ToggleSetting
                  label="Cache Enabled"
                  description="Cache embeddings for faster retrieval"
                  checked={settings.cache_enabled}
                  onChange={(checked) => setSettings({ ...settings, cache_enabled: checked })}
                />
                <ToggleSetting
                  label="OCR Enabled"
                  description="Enable optical character recognition for scanned PDFs"
                  checked={settings.ocr_enabled}
                  onChange={(checked) => setSettings({ ...settings, ocr_enabled: checked })}
                />
                <ToggleSetting
                  label="Claim Extraction"
                  description="Extract verifiable claims from answers"
                  checked={settings.claim_extraction_enabled}
                  onChange={(checked) => setSettings({ ...settings, claim_extraction_enabled: checked })}
                />
                <ToggleSetting
                  label="Faithfulness Check"
                  description="Verify answer faithfulness to source documents"
                  checked={settings.faithfulness_check_enabled}
                  onChange={(checked) => setSettings({ ...settings, faithfulness_check_enabled: checked })}
                />
              </div>
            </div>

            {/* System Info */}
            <div className="card">
              <div className="card-header">
                <h3 className="text-lg font-semibold">System Information</h3>
                <p className="text-sm text-[var(--color-text-secondary)] mt-1">Current system configuration</p>
              </div>
              <div className="card-body">
                <div className="space-y-3">
                  <InfoRow label="Max Upload Size" value={`${settings.max_upload_size_mb} MB`} />
                  <InfoRow label="Inline Worker" value={settings.inline_worker ? 'Enabled' : 'Disabled'} />
                  <InfoRow label="Cache" value={settings.cache_enabled ? 'Enabled' : 'Disabled'} />
                  <InfoRow label="OCR" value={settings.ocr_enabled ? 'Enabled' : 'Disabled'} />
                </div>
              </div>
            </div>

            <div className="flex justify-end">
              <button
                onClick={handleSave}
                disabled={saving}
                className="btn-primary px-8 disabled:opacity-50"
              >
                {saving ? (
                  <span className="flex items-center gap-2">
                    <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Saving...
                  </span>
                ) : 'Save Settings'}
              </button>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

function ToggleSetting({ label, description, checked, onChange }: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between py-3">
      <div>
        <p className="font-medium text-[var(--color-text-primary)]">{label}</p>
        <p className="text-sm text-[var(--color-text-secondary)]">{description}</p>
      </div>
      <button
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 ${
          checked ? 'bg-[var(--color-accent)]' : 'bg-[var(--color-bg-tertiary)]'
        }`}
      >
        <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform duration-200 ${
          checked ? 'translate-x-6' : 'translate-x-1'
        }`} />
      </button>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between py-3 border-b border-[var(--color-border)] last:border-0">
      <span className="text-[var(--color-text-secondary)]">{label}</span>
      <span className="font-medium text-[var(--color-text-primary)]">{value}</span>
    </div>
  );
}
