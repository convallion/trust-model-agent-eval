"use client";

import Link from "next/link";
import { formatDistanceToNow } from "date-fns";
import type { Agent } from "@/lib/api";
import { GradeBadge } from "@/components/ui/GradeBadge";
import { StatusBadge } from "@/components/ui/StatusBadge";

interface RecentAgentsProps {
  agents: Agent[];
}

export function RecentAgents({ agents }: RecentAgentsProps) {
  const recentAgents = agents.slice(0, 5);

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200">
      <div className="px-6 py-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">
            Registered Agents
          </h2>
          <Link
            href="/agents"
            className="text-sm font-medium text-primary-600 hover:text-primary-700"
          >
            View all
          </Link>
        </div>
      </div>
      <div className="divide-y divide-gray-200">
        {recentAgents.length === 0 ? (
          <div className="px-6 py-8 text-center text-gray-500">
            No agents registered yet.{" "}
            <Link href="/agents/new" className="text-primary-600">
              Register your first agent
            </Link>
          </div>
        ) : (
          recentAgents.map((agent) => (
            <Link
              key={agent.id}
              href={`/agents/${agent.id}`}
              className="flex items-center justify-between px-6 py-4 hover:bg-gray-50 transition-colors"
            >
              <div className="flex items-center gap-4">
                <div className="flex-shrink-0">
                  {agent.stats?.latest_certificate_grade ? (
                    <GradeBadge grade={agent.stats.latest_certificate_grade} />
                  ) : (
                    <div className="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center">
                      <span className="text-gray-400 text-sm">--</span>
                    </div>
                  )}
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-900">
                    {agent.name}
                  </p>
                  <p className="text-sm text-gray-500">
                    {agent.agent_type}
                    {agent.framework && ` · ${agent.framework}`}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <StatusBadge status={agent.status} />
                <span className="text-sm text-gray-500">
                  {formatDistanceToNow(new Date(agent.created_at), {
                    addSuffix: true,
                  })}
                </span>
              </div>
            </Link>
          ))
        )}
      </div>
    </div>
  );
}
