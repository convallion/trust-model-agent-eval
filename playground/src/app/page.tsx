"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";
import {
  PlusIcon,
  PlayIcon,
  CheckBadgeIcon,
  ClockIcon,
  ExclamationCircleIcon,
} from "@heroicons/react/24/outline";
import { SimpleLayout } from "@/components/layout/SimpleLayout";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

function GradeCircle({ grade }: { grade: string | null }) {
  const colors: Record<string, string> = {
    A: "bg-green-500",
    B: "bg-blue-500",
    C: "bg-yellow-500",
    D: "bg-orange-500",
    F: "bg-red-500",
  };

  if (!grade) {
    return (
      <div className="w-14 h-14 rounded-full bg-gray-200 flex items-center justify-center">
        <span className="text-gray-400 text-lg font-bold">--</span>
      </div>
    );
  }

  return (
    <div className={`w-14 h-14 rounded-full ${colors[grade] || "bg-gray-500"} flex items-center justify-center`}>
      <span className="text-white text-2xl font-bold">{grade}</span>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const config: Record<string, { color: string; icon: any; text: string }> = {
    running: { color: "bg-blue-100 text-blue-700", icon: ClockIcon, text: "Evaluating..." },
    completed: { color: "bg-green-100 text-green-700", icon: CheckBadgeIcon, text: "Evaluated" },
    failed: { color: "bg-red-100 text-red-700", icon: ExclamationCircleIcon, text: "Failed" },
    pending: { color: "bg-yellow-100 text-yellow-700", icon: ClockIcon, text: "Pending" },
  };

  const c = config[status] || config.pending;
  const Icon = c.icon;

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${c.color}`}>
      <Icon className="w-3 h-3" />
      {c.text}
    </span>
  );
}

export default function HomePage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.replace("/login");
    }
  }, [authLoading, isAuthenticated, router]);

  const { data: agents, isLoading } = useQuery({
    queryKey: ["agents"],
    queryFn: () => api.getAgents(),
    enabled: isAuthenticated,
  });

  const { data: evaluations } = useQuery({
    queryKey: ["evaluations"],
    queryFn: () => api.getEvaluations(),
    enabled: isAuthenticated,
  });

  // Show loading while checking auth
  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  // Don't render if not authenticated (redirect will happen)
  if (!isAuthenticated) {
    return null;
  }

  // Get latest evaluation for each agent
  const getLatestEval = (agentId: string) => {
    return evaluations?.items?.find((e) => e.agent_id === agentId);
  };

  return (
    <SimpleLayout>
      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary-600"></div>
        </div>
      ) : !agents?.items?.length ? (
        /* Empty State */
        <div className="text-center py-20">
          <div className="w-20 h-20 bg-primary-100 rounded-full flex items-center justify-center mx-auto mb-6">
            <PlusIcon className="w-10 h-10 text-primary-600" />
          </div>
          <h1 className="text-3xl font-bold text-gray-900 mb-3">
            Evaluate Your First Agent
          </h1>
          <p className="text-gray-500 mb-8 max-w-md mx-auto">
            Connect your LangGraph agent and run an evaluation in under 2 minutes.
          </p>
          <Link
            href="/new"
            className="inline-flex items-center gap-2 bg-primary-600 text-white px-8 py-4 rounded-xl font-semibold text-lg hover:bg-primary-700 transition-colors"
          >
            <PlusIcon className="w-6 h-6" />
            Add Your Agent
          </Link>
        </div>
      ) : (
        /* Agent List */
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-gray-900">Your Agents</h1>
            <Link
              href="/new"
              className="inline-flex items-center gap-2 bg-primary-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-primary-700 transition-colors"
            >
              <PlusIcon className="w-5 h-5" />
              Add Agent
            </Link>
          </div>

          <div className="grid gap-4">
            {agents.items.map((agent) => {
              const latestEval = getLatestEval(agent.id);

              return (
                <Link
                  key={agent.id}
                  href={`/agents/${agent.id}`}
                  className="bg-white rounded-xl border border-gray-200 p-6 hover:shadow-lg hover:border-gray-300 transition-all"
                >
                  <div className="flex items-center gap-6">
                    {/* Grade */}
                    <GradeCircle grade={latestEval?.grade || null} />

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3">
                        <h2 className="text-xl font-semibold text-gray-900 truncate">
                          {agent.name}
                        </h2>
                        {latestEval && <StatusPill status={latestEval.status} />}
                      </div>
                      <p className="text-gray-500 mt-1 truncate">
                        {agent.description || agent.framework || "LangGraph Agent"}
                      </p>
                      <p className="text-sm text-gray-400 mt-2">
                        Added {formatDistanceToNow(new Date(agent.created_at), { addSuffix: true })}
                      </p>
                    </div>

                    {/* Score */}
                    {latestEval?.scores?.overall && (
                      <div className="text-right">
                        <p className="text-3xl font-bold text-gray-900">
                          {latestEval.scores.overall.toFixed(0)}%
                        </p>
                        <p className="text-sm text-gray-500">Trust Score</p>
                      </div>
                    )}

                    {/* Action */}
                    {!latestEval && (
                      <button className="flex items-center gap-2 bg-green-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-green-700 transition-colors">
                        <PlayIcon className="w-5 h-5" />
                        Evaluate
                      </button>
                    )}
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      )}
    </SimpleLayout>
  );
}
