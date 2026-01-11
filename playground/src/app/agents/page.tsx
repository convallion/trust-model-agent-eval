"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";
import { PlusIcon, XMarkIcon } from "@heroicons/react/24/outline";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { api } from "@/lib/api";
import { GradeBadge } from "@/components/ui/GradeBadge";
import { StatusBadge } from "@/components/ui/StatusBadge";

export default function AgentsPage() {
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createError, setCreateError] = useState("");
  const queryClient = useQueryClient();

  const { data: agents, isLoading, error } = useQuery({
    queryKey: ["agents"],
    queryFn: () => api.getAgents(),
  });

  const createMutation = useMutation({
    mutationFn: api.createAgent,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agents"] });
      setIsCreateOpen(false);
      setCreateError("");
    },
    onError: (error: any) => {
      setCreateError(error.response?.data?.detail || "Failed to create agent");
    },
  });

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Agents</h1>
            <p className="mt-1 text-sm text-gray-500">
              Manage your registered AI agents
            </p>
          </div>
          <button
            onClick={() => setIsCreateOpen(true)}
            className="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 transition-colors"
          >
            <PlusIcon className="h-5 w-5" />
            Register Agent
          </button>
        </div>

        {/* Agent Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {isLoading ? (
            <div className="col-span-full flex justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
            </div>
          ) : error ? (
            <div className="col-span-full bg-red-50 border border-red-200 rounded-xl p-6 text-center">
              <p className="text-red-700">Failed to load agents. Please try again.</p>
            </div>
          ) : agents?.items.length === 0 ? (
            <div className="col-span-full bg-white rounded-xl shadow-sm border border-gray-200 p-8 text-center">
              <div className="max-w-sm mx-auto">
                <div className="w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <PlusIcon className="h-8 w-8 text-primary-600" />
                </div>
                <h3 className="text-lg font-semibold text-gray-900 mb-2">No agents yet</h3>
                <p className="text-gray-500 mb-4">
                  Register your first AI agent to start tracking and evaluating its behavior.
                </p>
                <button
                  onClick={() => setIsCreateOpen(true)}
                  className="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
                >
                  <PlusIcon className="h-5 w-5" />
                  Register Your First Agent
                </button>
              </div>
            </div>
          ) : (
            agents?.items.map((agent) => (
              <Link
                key={agent.id}
                href={`/agents/${agent.id}`}
                className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    {agent.stats?.latest_certificate_grade ? (
                      <GradeBadge grade={agent.stats.latest_certificate_grade} />
                    ) : (
                      <div className="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center">
                        <span className="text-gray-400 text-sm">--</span>
                      </div>
                    )}
                    <div>
                      <h3 className="font-semibold text-gray-900">{agent.name}</h3>
                      <p className="text-sm text-gray-500">{agent.agent_type}</p>
                    </div>
                  </div>
                  <StatusBadge status={agent.status} />
                </div>

                {agent.description && (
                  <p className="mt-3 text-sm text-gray-600 line-clamp-2">
                    {agent.description}
                  </p>
                )}

                <div className="mt-4 pt-4 border-t border-gray-100 flex justify-between text-sm text-gray-500">
                  <span>{agent.stats?.total_traces || 0} traces</span>
                  <span>{agent.stats?.total_evaluations || 0} evals</span>
                  <span>
                    {formatDistanceToNow(new Date(agent.created_at), {
                      addSuffix: true,
                    })}
                  </span>
                </div>
              </Link>
            ))
          )}
        </div>

        {/* Create Modal */}
        {isCreateOpen && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-white rounded-xl shadow-xl max-w-md w-full mx-4 p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-gray-900">
                  Register New Agent
                </h2>
                <button
                  onClick={() => {
                    setIsCreateOpen(false);
                    setCreateError("");
                  }}
                  className="text-gray-400 hover:text-gray-500"
                >
                  <XMarkIcon className="h-6 w-6" />
                </button>
              </div>

              {createError && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                  {createError}
                </div>
              )}

              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const formData = new FormData(e.currentTarget);
                  createMutation.mutate({
                    name: formData.get("name") as string,
                    agent_type: formData.get("type") as string,
                    description: formData.get("description") as string,
                    framework: formData.get("framework") as string,
                  });
                }}
                className="space-y-4"
              >
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Agent Name
                  </label>
                  <input
                    name="name"
                    type="text"
                    required
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    placeholder="my-claude-agent"
                  />
                  <p className="mt-1 text-xs text-gray-500">
                    A unique identifier for your agent
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Type
                  </label>
                  <select
                    name="type"
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 focus:ring-2 focus:ring-primary-500"
                  >
                    <option value="coding">Coding Assistant</option>
                    <option value="conversational">Conversational</option>
                    <option value="research">Research Agent</option>
                    <option value="analysis">Analysis</option>
                    <option value="automation">Automation</option>
                    <option value="custom">Custom</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Framework
                  </label>
                  <select
                    name="framework"
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 focus:ring-2 focus:ring-primary-500"
                  >
                    <option value="anthropic-api">Anthropic API (Direct)</option>
                    <option value="claude-code">Claude Code (Local Proxy)</option>
                    <option value="langchain">LangChain</option>
                    <option value="openai">OpenAI Compatible</option>
                    <option value="custom">Custom</option>
                  </select>
                  <p className="mt-1 text-xs text-gray-500">
                    How to connect to this agent
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Description
                  </label>
                  <textarea
                    name="description"
                    rows={3}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 focus:ring-2 focus:ring-primary-500"
                    placeholder="Describe what this agent does..."
                  />
                </div>
                <div className="flex gap-3 justify-end pt-4">
                  <button
                    type="button"
                    onClick={() => {
                      setIsCreateOpen(false);
                      setCreateError("");
                    }}
                    className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-lg"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={createMutation.isPending}
                    className="px-4 py-2 text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 rounded-lg disabled:opacity-50"
                  >
                    {createMutation.isPending ? "Creating..." : "Register Agent"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
