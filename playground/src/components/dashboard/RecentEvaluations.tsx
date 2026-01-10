"use client";

import Link from "next/link";
import { formatDistanceToNow } from "date-fns";
import type { Evaluation } from "@/lib/api";
import { GradeBadge } from "@/components/ui/GradeBadge";
import { StatusBadge } from "@/components/ui/StatusBadge";

interface RecentEvaluationsProps {
  evaluations: Evaluation[];
}

export function RecentEvaluations({ evaluations }: RecentEvaluationsProps) {
  const recentEvals = evaluations.slice(0, 5);

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200">
      <div className="px-6 py-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">
            Recent Evaluations
          </h2>
          <Link
            href="/evaluations"
            className="text-sm font-medium text-primary-600 hover:text-primary-700"
          >
            View all
          </Link>
        </div>
      </div>
      <div className="divide-y divide-gray-200">
        {recentEvals.length === 0 ? (
          <div className="px-6 py-8 text-center text-gray-500">
            No evaluations run yet.
          </div>
        ) : (
          recentEvals.map((evaluation) => (
            <Link
              key={evaluation.id}
              href={`/evaluations/${evaluation.id}`}
              className="flex items-center justify-between px-6 py-4 hover:bg-gray-50 transition-colors"
            >
              <div className="flex items-center gap-4">
                <div className="flex-shrink-0">
                  {evaluation.grade ? (
                    <GradeBadge grade={evaluation.grade} />
                  ) : (
                    <div className="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center">
                      <span className="text-gray-400 text-sm">--</span>
                    </div>
                  )}
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-900">
                    Agent {evaluation.agent_id.slice(0, 8)}...
                  </p>
                  <p className="text-sm text-gray-500">
                    {evaluation.suites.join(", ")}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                {evaluation.scores && (
                  <span className="text-sm font-medium text-gray-900">
                    {evaluation.scores.overall.toFixed(1)}%
                  </span>
                )}
                <StatusBadge status={evaluation.status} />
                <span className="text-sm text-gray-500">
                  {formatDistanceToNow(new Date(evaluation.started_at), {
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
