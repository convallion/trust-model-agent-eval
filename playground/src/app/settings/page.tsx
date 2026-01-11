"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const [showApiKey, setShowApiKey] = useState(false);
  const [newApiKeyName, setNewApiKeyName] = useState("");
  const [createdApiKey, setCreatedApiKey] = useState<string | null>(null);

  const createApiKeyMutation = useMutation({
    mutationFn: (name: string) => api.createApiKey(name),
    onSuccess: (data) => {
      setCreatedApiKey(data.key);
      setNewApiKeyName("");
    },
  });

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage your account and API keys
          </p>
        </div>

        {/* Account Info */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Account</h2>
          <dl className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <dt className="text-sm text-gray-500">Email</dt>
              <dd className="font-medium text-gray-900">{user?.email || "—"}</dd>
            </div>
            <div>
              <dt className="text-sm text-gray-500">Organization</dt>
              <dd className="font-medium text-gray-900">
                {user?.organization_id || "Default Organization"}
              </dd>
            </div>
          </dl>
          <div className="mt-6 pt-4 border-t border-gray-100">
            <button
              onClick={logout}
              className="px-4 py-2 text-sm font-medium text-red-600 hover:text-red-700 hover:bg-red-50 rounded-lg transition-colors"
            >
              Sign Out
            </button>
          </div>
        </div>

        {/* API Keys */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">API Keys</h2>
          <p className="text-sm text-gray-600 mb-4">
            Create API keys to authenticate your agents with the TrustModel server.
          </p>

          {/* Create new API key */}
          <div className="mb-6">
            <div className="flex gap-3">
              <input
                type="text"
                value={newApiKeyName}
                onChange={(e) => setNewApiKeyName(e.target.value)}
                placeholder="API key name (e.g., my-agent-key)"
                className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              />
              <button
                onClick={() => createApiKeyMutation.mutate(newApiKeyName || "default")}
                disabled={createApiKeyMutation.isPending}
                className="px-4 py-2 text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 rounded-lg disabled:opacity-50"
              >
                {createApiKeyMutation.isPending ? "Creating..." : "Create Key"}
              </button>
            </div>
          </div>

          {/* Show created key */}
          {createdApiKey && (
            <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg">
              <p className="text-sm text-green-800 mb-2">
                API key created successfully. Copy it now - it won&apos;t be shown again!
              </p>
              <div className="flex items-center gap-2">
                <code className="flex-1 bg-white px-3 py-2 rounded border text-sm font-mono">
                  {createdApiKey}
                </code>
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(createdApiKey);
                  }}
                  className="px-3 py-2 text-sm font-medium text-primary-600 hover:bg-primary-50 rounded-lg"
                >
                  Copy
                </button>
              </div>
            </div>
          )}

          {/* Usage instructions */}
          <div className="bg-gray-50 rounded-lg p-4">
            <h3 className="text-sm font-medium text-gray-900 mb-2">
              Using API Keys
            </h3>
            <pre className="text-xs text-gray-600 overflow-x-auto">
{`from trustmodel import instrument

handle = instrument(
    agent_name="my-agent",
    api_key="tm_your_api_key_here",
    server_url="http://localhost:8000"
)

# Your agent code...

handle.shutdown()`}
            </pre>
          </div>
        </div>

        {/* Server Configuration */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Server Configuration
          </h2>
          <dl className="space-y-3">
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">API Endpoint</dt>
              <dd className="font-mono text-sm text-gray-900">
                http://localhost:8000
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm text-gray-500">WebSocket Endpoint</dt>
              <dd className="font-mono text-sm text-gray-900">
                ws://localhost:8000/v1/sessions
              </dd>
            </div>
          </dl>
        </div>
      </div>
    </DashboardLayout>
  );
}
