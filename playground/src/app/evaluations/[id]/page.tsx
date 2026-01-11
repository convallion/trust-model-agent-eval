"use client";

import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { formatDistanceToNow, format } from "date-fns";
import {
  ArrowLeftIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  DocumentArrowDownIcon,
} from "@heroicons/react/24/outline";
import Link from "next/link";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { api } from "@/lib/api";
import { GradeBadge } from "@/components/ui/GradeBadge";
import { StatusBadge } from "@/components/ui/StatusBadge";

function ScoreBar({ score, label }: { score: number | undefined; label: string }) {
  if (score === undefined) {
    return (
      <div className="space-y-2">
        <div className="flex justify-between items-center">
          <span className="text-sm font-medium text-gray-700 capitalize">{label}</span>
          <span className="text-sm text-gray-400">Pending...</span>
        </div>
        <div className="h-3 bg-gray-200 rounded-full overflow-hidden">
          <div className="h-full bg-gray-300 animate-pulse w-1/3"></div>
        </div>
      </div>
    );
  }

  const getColor = (s: number) => {
    if (s >= 90) return "bg-green-500";
    if (s >= 80) return "bg-emerald-500";
    if (s >= 70) return "bg-yellow-500";
    if (s >= 60) return "bg-orange-500";
    return "bg-red-500";
  };

  return (
    <div className="space-y-2">
      <div className="flex justify-between items-center">
        <span className="text-sm font-medium text-gray-700 capitalize">{label}</span>
        <span className={`text-sm font-semibold ${score >= 70 ? "text-green-600" : score >= 50 ? "text-yellow-600" : "text-red-600"}`}>
          {score.toFixed(1)}%
        </span>
      </div>
      <div className="h-3 bg-gray-200 rounded-full overflow-hidden">
        <div
          className={`h-full ${getColor(score)} transition-all duration-500`}
          style={{ width: `${score}%` }}
        ></div>
      </div>
    </div>
  );
}

export default function EvaluationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();

  const { data: evaluation, isLoading, error } = useQuery({
    queryKey: ["evaluation", id],
    queryFn: () => api.getEvaluation(id),
    enabled: !!id,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "running" || status === "pending" ? 2000 : false;
    },
  });

  const issueCertMutation = useMutation({
    mutationFn: () => api.issueCertificate(evaluation!.agent_id, evaluation!.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["evaluation", id] });
    },
  });

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
        </div>
      </DashboardLayout>
    );
  }

  if (error || !evaluation) {
    return (
      <DashboardLayout>
        <div className="text-center py-12">
          <p className="text-red-600 mb-4">Failed to load evaluation</p>
          <Link href="/evaluations" className="text-primary-600 hover:underline">
            Back to evaluations
          </Link>
        </div>
      </DashboardLayout>
    );
  }

  const isRunning = evaluation.status === "running" || evaluation.status === "pending";
  const isCompleted = evaluation.status === "completed";
  const canIssueCert = isCompleted && !evaluation.certificate_id && (evaluation.scores?.overall ?? 0) >= 60;

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link
              href={`/agents/${evaluation.agent_id}`}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <ArrowLeftIcon className="h-5 w-5 text-gray-500" />
            </Link>
            <div className="flex items-center gap-3">
              {evaluation.grade ? (
                <GradeBadge grade={evaluation.grade} size="lg" />
              ) : (
                <div className="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center">
                  {isRunning ? (
                    <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary-600"></div>
                  ) : (
                    <span className="text-gray-400 text-lg">--</span>
                  )}
                </div>
              )}
              <div>
                <h1 className="text-2xl font-bold text-gray-900">
                  Evaluation Results
                </h1>
                <p className="text-sm text-gray-500">
                  {isRunning ? "Running..." : `Completed ${formatDistanceToNow(new Date(evaluation.completed_at || evaluation.started_at), { addSuffix: true })}`}
                </p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {canIssueCert && (
              <button
                onClick={() => issueCertMutation.mutate()}
                disabled={issueCertMutation.isPending}
                className="inline-flex items-center gap-2 rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
              >
                <DocumentArrowDownIcon className="h-5 w-5" />
                {issueCertMutation.isPending ? "Issuing..." : "Issue Certificate"}
              </button>
            )}
            <StatusBadge status={evaluation.status} />
          </div>
        </div>

        {/* Running State Banner */}
        {isRunning && (
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 flex items-center gap-4">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            <div>
              <p className="font-medium text-blue-900">Evaluation in progress</p>
              <p className="text-sm text-blue-700">Testing {evaluation.suites.join(", ")} suites. This may take a few minutes...</p>
            </div>
          </div>
        )}

        {/* Main Content */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            {/* Score Overview */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-lg font-semibold text-gray-900">Score Breakdown</h2>
                {evaluation.scores?.overall !== undefined && (
                  <div className="text-right">
                    <p className="text-3xl font-bold text-gray-900">{evaluation.scores.overall.toFixed(1)}%</p>
                    <p className="text-sm text-gray-500">Overall Score</p>
                  </div>
                )}
              </div>
              <div className="space-y-4">
                {evaluation.suites.includes("capability") && (
                  <ScoreBar score={evaluation.scores?.capability} label="Capability" />
                )}
                {evaluation.suites.includes("safety") && (
                  <ScoreBar score={evaluation.scores?.safety} label="Safety" />
                )}
                {evaluation.suites.includes("reliability") && (
                  <ScoreBar score={evaluation.scores?.reliability} label="Reliability" />
                )}
                {evaluation.suites.includes("communication") && (
                  <ScoreBar score={evaluation.scores?.communication} label="Communication" />
                )}
              </div>
            </div>

            {/* Suite Details */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-200">
              <div className="px-6 py-4 border-b border-gray-200">
                <h2 className="text-lg font-semibold text-gray-900">Suite Details</h2>
              </div>
              <div className="divide-y divide-gray-200">
                {evaluation.suites.map((suite) => {
                  const score = evaluation.scores?.[suite as keyof typeof evaluation.scores];
                  const passed = typeof score === "number" && score >= 70;

                  return (
                    <div key={suite} className="px-6 py-4">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-3">
                          {typeof score === "number" ? (
                            passed ? (
                              <CheckCircleIcon className="h-6 w-6 text-green-500" />
                            ) : (
                              <XCircleIcon className="h-6 w-6 text-red-500" />
                            )
                          ) : (
                            <ClockIcon className="h-6 w-6 text-gray-400" />
                          )}
                          <span className="font-medium text-gray-900 capitalize">{suite}</span>
                        </div>
                        {typeof score === "number" && (
                          <span className={`text-lg font-semibold ${passed ? "text-green-600" : "text-red-600"}`}>
                            {score.toFixed(1)}%
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-gray-500 ml-9">
                        {suite === "capability" && "Tests task completion, tool usage, and following instructions"}
                        {suite === "safety" && "Tests for harmful outputs, prompt injection, and policy compliance"}
                        {suite === "reliability" && "Tests consistency, error handling, and graceful degradation"}
                        {suite === "communication" && "Tests clarity, tone appropriateness, and protocol adherence"}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Results Details */}
            {evaluation.results && Object.keys(evaluation.results).length > 0 && (
              <div className="bg-white rounded-xl shadow-sm border border-gray-200">
                <div className="px-6 py-4 border-b border-gray-200">
                  <h2 className="text-lg font-semibold text-gray-900">Detailed Results</h2>
                </div>
                <div className="p-6">
                  <pre className="bg-gray-900 text-gray-100 rounded-lg p-4 text-sm overflow-auto max-h-96">
                    {JSON.stringify(evaluation.results, null, 2)}
                  </pre>
                </div>
              </div>
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Grade Card */}
            <div className="bg-gradient-to-br from-gray-800 to-gray-900 rounded-xl p-6 text-white">
              <p className="text-sm text-gray-400 mb-2">Final Grade</p>
              {evaluation.grade ? (
                <div className="flex items-center gap-4">
                  <span className={`text-6xl font-bold ${
                    evaluation.grade === "A" ? "text-green-400" :
                    evaluation.grade === "B" ? "text-blue-400" :
                    evaluation.grade === "C" ? "text-yellow-400" :
                    evaluation.grade === "D" ? "text-orange-400" :
                    "text-red-400"
                  }`}>
                    {evaluation.grade}
                  </span>
                  <div>
                    <p className="text-lg font-semibold">
                      {evaluation.grade === "A" ? "Excellent" :
                       evaluation.grade === "B" ? "Good" :
                       evaluation.grade === "C" ? "Satisfactory" :
                       evaluation.grade === "D" ? "Needs Improvement" :
                       "Unsatisfactory"}
                    </p>
                    <p className="text-sm text-gray-400">
                      {evaluation.scores?.overall?.toFixed(1)}% overall
                    </p>
                  </div>
                </div>
              ) : (
                <div className="flex items-center gap-4">
                  <span className="text-6xl font-bold text-gray-500">?</span>
                  <p className="text-gray-400">Awaiting results...</p>
                </div>
              )}
            </div>

            {/* Metadata */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Details</h2>
              <dl className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <dt className="text-gray-500">Evaluation ID</dt>
                  <dd className="font-mono text-gray-900">{evaluation.id.slice(0, 8)}...</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-500">Agent</dt>
                  <dd>
                    <Link
                      href={`/agents/${evaluation.agent_id}`}
                      className="text-primary-600 hover:underline"
                    >
                      {evaluation.agent_id.slice(0, 8)}...
                    </Link>
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-500">Started</dt>
                  <dd className="text-gray-900">
                    {format(new Date(evaluation.started_at), "PPp")}
                  </dd>
                </div>
                {evaluation.completed_at && (
                  <div className="flex justify-between">
                    <dt className="text-gray-500">Completed</dt>
                    <dd className="text-gray-900">
                      {format(new Date(evaluation.completed_at), "PPp")}
                    </dd>
                  </div>
                )}
              </dl>
            </div>

            {/* Suites */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Suites Tested</h2>
              <div className="flex flex-wrap gap-2">
                {evaluation.suites.map((suite) => (
                  <span
                    key={suite}
                    className="inline-flex items-center rounded-full px-3 py-1 text-sm font-medium bg-primary-100 text-primary-700 capitalize"
                  >
                    {suite}
                  </span>
                ))}
              </div>
            </div>

            {/* Certificate */}
            {evaluation.certificate_id ? (
              <div className="bg-green-50 border border-green-200 rounded-xl p-6">
                <h2 className="text-lg font-semibold text-green-800 mb-2">Certificate Issued</h2>
                <p className="text-sm text-green-700 mb-4">
                  A trust certificate has been issued based on this evaluation.
                </p>
                <Link
                  href={`/certificates/${evaluation.certificate_id}`}
                  className="inline-flex items-center gap-2 bg-green-600 text-white rounded-lg px-4 py-2 text-sm font-medium hover:bg-green-700 transition-colors"
                >
                  View Certificate
                </Link>
              </div>
            ) : canIssueCert ? (
              <div className="bg-blue-50 border border-blue-200 rounded-xl p-6">
                <h2 className="text-lg font-semibold text-blue-800 mb-2">Issue Certificate</h2>
                <p className="text-sm text-blue-700 mb-4">
                  This agent passed the evaluation. You can now issue a trust certificate.
                </p>
                <button
                  onClick={() => issueCertMutation.mutate()}
                  disabled={issueCertMutation.isPending}
                  className="inline-flex items-center gap-2 bg-blue-600 text-white rounded-lg px-4 py-2 text-sm font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
                >
                  <DocumentArrowDownIcon className="h-4 w-4" />
                  {issueCertMutation.isPending ? "Issuing..." : "Issue Certificate"}
                </button>
              </div>
            ) : isCompleted && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-6">
                <h2 className="text-lg font-semibold text-yellow-800 mb-2">No Certificate</h2>
                <p className="text-sm text-yellow-700">
                  The agent did not meet the minimum score (60%) required for certification.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
