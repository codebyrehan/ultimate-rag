import { useEffect, useState } from 'react';

export default function SettingsPage() {
  const [settings, setSettings] = useState<Record<string, unknown>>({});

  useEffect(() => {
    fetch('/ready')
      .then((r) => r.json())
      .then(setSettings)
      .catch(console.error);
  }, []);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow">
        <div className="max-w-4xl mx-auto px-4 py-3 flex justify-between items-center">
          <h1 className="text-lg font-bold">Settings</h1>
          <a href="/" className="text-blue-600 hover:text-blue-800">
            ← Back
          </a>
        </div>
      </header>

      <main className="max-w-4xl mx-auto py-6 px-4">
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="font-semibold text-lg mb-4">System Configuration</h2>
          <pre className="whitespace-pre-wrap text-sm bg-gray-50 p-4 rounded">
            {JSON.stringify(settings, null, 2)}
          </pre>
        </div>
      </main>
    </div>
  );
}
