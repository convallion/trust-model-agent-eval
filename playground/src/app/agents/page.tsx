"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";
import { PlusIcon } from "@heroicons/react/24/outline";
import { api } from "@/lib/api";
import { GradeBadge } from "@/components/ui/GradeBadge";
import { StatusBadge } from "@/components/ui/StatusBadge";

export default function AgentsPage() {
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const queryClient = useQueryClient();

  const { data: agents, isLoading } = useQuery({
    queryKey: ["agents"],
    queryFn: () => api.getAgents(),
  });

  return (
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
          <div className="col-span-full text-center py-8 text-gray-500">
            Loading agents...
          </div>
        ) : agents?.items.length === 0 ? (
          <div className="col-span-full bg-white rounded-xl shadow-sm border border-gray-200 p-8 text-center">
            <p className="text-gray-500 mb-4">No agents registered yet.</p>
            <button
              onClick={() => setIsCreateOpen(true)}
              className="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
            >
              <PlusIcon className="h-5 w-5" />
              Register Your First Agent
            </button>
          </div>
        ) : (
          agents?.items.map((agent) => (
            <Link
              key={agent.id}
              href={`/agents/${agent.id}`}
              className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 card-hover"
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
                <span>
                  {agent.stats?.total_traces || 0} traces
                </span>
                <span>
                  {agent.stats?.total_evaluations || 0} evals
                </span>
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

      {/* Create Modal (simplified) */}
      {isCreateOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Register New Agent
            </h2>
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                const formData = new FormData(e.currentTarget);
                await api.createAgent({
                  name: formData.get("name") as string,
                  agent_type: formData.get("type") as string,
                  description: formData.get("description") as string,
                });
                queryClient.invalidateQueries({ queryKey: ["agents"] });
                setIsCreateOpen(false);
              }}
              className="space-y-4"
            >
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Name
                </label>
                <input
                  name="name"
                  type="text"
                  required
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  placeholder="my-agent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Type
                </label>
                <select
                  name="type"
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 focus:ring-2 focus:ring-primary-500"
                >
                  <option value="coding">Coding</option>
                  <option value="research">Research</option>
                  <option value="assistant">Assistant</option>
                  <option value="orchestrator">Orchestrator</option>
                  <option value="custom">Custom</option>
                </select>
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
              <div className="flex gap-3 justify-end">
                <button
                  type="button"
                  onClick={() => setIsCreateOpen(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 rounded-lg"
                >
                  Register
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
