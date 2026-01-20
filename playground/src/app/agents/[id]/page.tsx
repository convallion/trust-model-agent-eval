"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";
import {
  ArrowLeftIcon,
  PlayIcon,
  ArrowPathIcon,
  ChatBubbleLeftRightIcon,
  ChartBarIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  BeakerIcon,
  ShieldCheckIcon,
  CogIcon,
  DocumentCheckIcon,
  ClipboardDocumentIcon,
  ExclamationTriangleIcon,
} from "@heroicons/react/24/outline";
import Link from "next/link";
import { SimpleLayout } from "@/components/layout/SimpleLayout";
import { api, Evaluation } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { TraceDetail } from "./trace-detail";

// Helper to get scores from evaluation (handles both flat and nested formats)
function getEvalScores(evaluation: Evaluation) {
  return {
    overall: evaluation.overall_score ?? evaluation.scores?.overall,
    capability: evaluation.capability_score ?? evaluation.scores?.capability,
    safety: evaluation.safety_score ?? evaluation.scores?.safety,
    reliability: evaluation.reliability_score ?? evaluation.scores?.reliability,
    communication: evaluation.communication_score ?? evaluation.scores?.communication,
  };
}

// Certificate eligibility requirements
const CERT_MIN_OVERALL_SCORE = 70;
const CERT_MIN_SAFETY_SCORE = 85;

// Check if evaluation is eligible for certificate issuance
function getEvalEligibility(evaluation: Evaluation): { eligible: boolean; reasons: string[] } {
  // If backend already computed eligibility, use it
  if (evaluation.certificate_eligible !== undefined) {
    return {
      eligible: evaluation.certificate_eligible,
      reasons: evaluation.certificate_eligible ? [] : ["Does not meet certificate requirements"]
    };
  }

  const scores = getEvalScores(evaluation);
  const reasons: string[] = [];

  if (scores.overall === undefined) {
    reasons.push("No overall score available");
  } else if (scores.overall < CERT_MIN_OVERALL_SCORE) {
    reasons.push(`Overall score ${scores.overall.toFixed(0)}% is below required ${CERT_MIN_OVERALL_SCORE}%`);
  }

  if (scores.safety === undefined) {
    reasons.push("No safety score available");
  } else if (scores.safety < CERT_MIN_SAFETY_SCORE) {
    reasons.push(`Safety score ${scores.safety.toFixed(0)}% is below required ${CERT_MIN_SAFETY_SCORE}%`);
  }

  return { eligible: reasons.length === 0, reasons };
}

type TabType = "traces" | "evaluations" | "certificates" | "setup";

interface Certificate {
  id: string;
  version: string;
  agent_id: string;
  agent_name: string | null;
  organization_name: string | null;
  evaluation_id: string;
  status: "active" | "revoked" | "expired";
  issued_at: string;
  expires_at: string;
  days_until_expiry: number;
  grade: string;
  overall_score: number;
  capability_score: number | null;
  safety_score: number | null;
  reliability_score: number | null;
  communication_score: number | null;
  certified_capabilities: string[];
  not_certified: string[];
  safety_attestations: { type: string; tests_passed: number; pass_rate: number }[];
  signature: string;
  created_at: string;
}

interface LangGraphTrace {
  id: string;
  created_at: string;
  updated_at: string;
  status: string;
  runs: any[];
  messages: any[];
  lastMessage: string | null;
  metadata: Record<string, any>;
}

function GradeCircle({ grade, size = "md" }: { grade: string | null; size?: "sm" | "md" | "lg" }) {
  const colors: Record<string, string> = {
    A: "bg-green-500",
    B: "bg-blue-500",
    C: "bg-yellow-500",
    D: "bg-orange-500",
    F: "bg-red-500",
  };

  const sizes = {
    sm: "w-8 h-8 text-sm",
    md: "w-12 h-12 text-xl",
    lg: "w-16 h-16 text-2xl",
  };

  if (!grade) {
    return (
      <div className={`${sizes[size]} rounded-full bg-gray-200 flex items-center justify-center`}>
        <span className="text-gray-400 font-bold">--</span>
      </div>
    );
  }

  return (
    <div className={`${sizes[size]} rounded-full ${colors[grade] || "bg-gray-500"} flex items-center justify-center`}>
      <span className="text-white font-bold">{grade}</span>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const config: Record<string, { color: string; icon: any; label: string }> = {
    running: { color: "bg-blue-100 text-blue-700", icon: ClockIcon, label: "Running" },
    completed: { color: "bg-green-100 text-green-700", icon: CheckCircleIcon, label: "Completed" },
    failed: { color: "bg-red-100 text-red-700", icon: XCircleIcon, label: "Failed" },
    pending: { color: "bg-yellow-100 text-yellow-700", icon: ClockIcon, label: "Pending" },
    idle: { color: "bg-gray-100 text-gray-700", icon: CheckCircleIcon, label: "Idle" },
    busy: { color: "bg-blue-100 text-blue-700", icon: ClockIcon, label: "Busy" },
  };

  const c = config[status] || config.pending;
  const Icon = c.icon;

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${c.color}`}>
      <Icon className="w-3 h-3" />
      {c.label}
    </span>
  );
}

function TracesInfo({ url }: { url?: string }) {
  return (
    <div className="bg-blue-50 border border-blue-200 rounded-xl p-6">
      <h3 className="font-semibold text-blue-900 mb-2">How to see traces</h3>
      <p className="text-blue-800 text-sm mb-3">
        Chat with your agent using any of these methods, then click "Refresh" to see the conversations here:
      </p>
      <ul className="text-blue-700 text-sm space-y-2">
        <li className="flex items-start gap-2">
          <span className="font-medium">1.</span>
          <span>Use <strong>LangGraph Studio</strong> or <strong>LangSmith Playground</strong> to chat directly</span>
        </li>
        <li className="flex items-start gap-2">
          <span className="font-medium">2.</span>
          <span>Call your agent via the LangGraph API from your application</span>
        </li>
        <li className="flex items-start gap-2">
          <span className="font-medium">3.</span>
          <span>Use the LangGraph SDK in your code</span>
        </li>
      </ul>
      {url && (
        <div className="mt-4 p-3 bg-white rounded-lg border border-blue-200">
          <p className="text-xs text-blue-600 mb-1">Your agent URL:</p>
          <code className="text-xs text-blue-900 break-all">{url}</code>
        </div>
      )}
    </div>
  );
}

function EvaluationDetail({ evaluation }: { evaluation: Evaluation }) {
  const [expanded, setExpanded] = useState(false);

  // Parse results if available
  const results = evaluation.results as Record<string, any> | undefined;
  const scores = getEvalScores(evaluation);

  return (
    <div className="border-b border-gray-200 last:border-b-0">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-4">
          <GradeCircle grade={evaluation.grade || null} size="sm" />
          <div className="text-left">
            <p className="font-medium text-gray-900">
              {evaluation.suites?.join(", ") || "Evaluation"}
            </p>
            <p className="text-sm text-gray-500">
              {formatDistanceToNow(new Date(evaluation.started_at), { addSuffix: true })}
              {evaluation.completed_at && ` • Completed in ${Math.round((new Date(evaluation.completed_at).getTime() - new Date(evaluation.started_at).getTime()) / 1000)}s`}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          {scores.overall !== undefined && (
            <div className="text-right">
              <p className="font-semibold text-gray-900">
                {scores.overall.toFixed(0)}%
              </p>
            </div>
          )}
          <StatusPill status={evaluation.status} />
          {expanded ? (
            <ChevronUpIcon className="w-5 h-5 text-gray-400" />
          ) : (
            <ChevronDownIcon className="w-5 h-5 text-gray-400" />
          )}
        </div>
      </button>

      {expanded && (
        <div className="px-6 pb-6 bg-gray-50">
          {/* Score Breakdown */}
          {scores.overall !== undefined && (
            <div className="mb-6">
              <h4 className="text-sm font-medium text-gray-700 mb-3">Score Breakdown</h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-white rounded-lg p-3 border border-gray-200">
                  <p className="text-2xl font-bold text-gray-900">{scores.overall?.toFixed(0) || "--"}%</p>
                  <p className="text-xs text-gray-500">Overall</p>
                </div>
                {scores.capability !== undefined && (
                  <div className="bg-white rounded-lg p-3 border border-gray-200">
                    <p className="text-xl font-semibold text-gray-700">{scores.capability.toFixed(0)}%</p>
                    <p className="text-xs text-gray-500">Capability</p>
                  </div>
                )}
                {scores.safety !== undefined && (
                  <div className="bg-white rounded-lg p-3 border border-gray-200">
                    <p className="text-xl font-semibold text-gray-700">{scores.safety.toFixed(0)}%</p>
                    <p className="text-xs text-gray-500">Safety</p>
                  </div>
                )}
                {scores.reliability !== undefined && (
                  <div className="bg-white rounded-lg p-3 border border-gray-200">
                    <p className="text-xl font-semibold text-gray-700">{scores.reliability.toFixed(0)}%</p>
                    <p className="text-xs text-gray-500">Reliability</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Detailed Results */}
          {results && Object.keys(results).length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-3">Detailed Results</h4>
              <div className="space-y-4">
                {Object.entries(results).map(([suite, suiteResults]: [string, any]) => (
                  <div key={suite} className="bg-white rounded-lg border border-gray-200 overflow-hidden">
                    <div className="px-4 py-3 bg-gray-100 border-b border-gray-200 flex items-center gap-2">
                      {suite === "capability" && <BeakerIcon className="w-4 h-4 text-blue-600" />}
                      {suite === "safety" && <ShieldCheckIcon className="w-4 h-4 text-green-600" />}
                      {suite === "reliability" && <CogIcon className="w-4 h-4 text-purple-600" />}
                      <span className="font-medium text-gray-900 capitalize">{suite}</span>
                      {suiteResults.score !== undefined && (
                        <span className="ml-auto text-sm font-medium text-gray-600">
                          {(suiteResults.score * 100).toFixed(0)}%
                        </span>
                      )}
                    </div>
                    <div className="p-4">
                      {suiteResults.tests && Array.isArray(suiteResults.tests) ? (
                        <div className="space-y-3">
                          {suiteResults.tests.map((test: any, idx: number) => (
                            <div key={idx} className="flex items-start gap-3">
                              {test.passed ? (
                                <CheckCircleIcon className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
                              ) : (
                                <XCircleIcon className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                              )}
                              <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-gray-900">{test.name || `Test ${idx + 1}`}</p>
                                {test.description && (
                                  <p className="text-xs text-gray-500 mt-0.5">{test.description}</p>
                                )}
                                {test.details && (
                                  <p className="text-xs text-gray-600 mt-1 bg-gray-50 rounded p-2">{test.details}</p>
                                )}
                              </div>
                              {test.score !== undefined && (
                                <span className="text-sm text-gray-600">{(test.score * 100).toFixed(0)}%</span>
                              )}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-sm text-gray-500">
                          {typeof suiteResults === "object"
                            ? JSON.stringify(suiteResults, null, 2)
                            : String(suiteResults)
                          }
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* No detailed results */}
          {(!results || Object.keys(results).length === 0) && evaluation.status === "completed" && (
            <p className="text-sm text-gray-500">Evaluation completed. Detailed breakdown not available.</p>
          )}

          {evaluation.status === "running" && (
            <div className="flex items-center gap-2 text-blue-600">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
              <span className="text-sm">Evaluation in progress...</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function CertificateCard({
  certificate,
  onRevoke,
  onCopy
}: {
  certificate: Certificate;
  onRevoke: (id: string) => void;
  onCopy: (text: string, label: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const isActive = certificate.status === "active";
  const isExpired = certificate.status === "expired";
  const isRevoked = certificate.status === "revoked";

  const statusColors = {
    active: "bg-green-100 text-green-700 border-green-200",
    expired: "bg-yellow-100 text-yellow-700 border-yellow-200",
    revoked: "bg-red-100 text-red-700 border-red-200",
  };

  return (
    <div className={`border rounded-xl overflow-hidden ${isActive ? "border-green-200" : "border-gray-200"}`}>
      <button
        onClick={() => setExpanded(!expanded)}
        className={`w-full px-6 py-4 flex items-center justify-between transition-colors ${
          isActive ? "bg-green-50 hover:bg-green-100" : "bg-gray-50 hover:bg-gray-100"
        }`}
      >
        <div className="flex items-center gap-4">
          <GradeCircle grade={certificate.grade} size="sm" />
          <div className="text-left">
            <div className="flex items-center gap-2">
              <p className="font-medium text-gray-900">Trust Certificate</p>
              <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColors[certificate.status]}`}>
                {certificate.status.charAt(0).toUpperCase() + certificate.status.slice(1)}
              </span>
            </div>
            <p className="text-sm text-gray-500">
              Issued {formatDistanceToNow(new Date(certificate.issued_at), { addSuffix: true })}
              {isActive && ` • Expires in ${certificate.days_until_expiry} days`}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <p className="text-lg font-semibold text-gray-700">{(certificate.overall_score * 100).toFixed(0)}%</p>
          {expanded ? (
            <ChevronUpIcon className="w-5 h-5 text-gray-400" />
          ) : (
            <ChevronDownIcon className="w-5 h-5 text-gray-400" />
          )}
        </div>
      </button>

      {expanded && (
        <div className="px-6 py-5 bg-white space-y-5">
          {/* Certificate ID - Most Important for Collaboration */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-medium text-blue-800">Certificate ID (for Agent Collaboration)</p>
              <button
                onClick={() => onCopy(certificate.id, "Certificate ID")}
                className="text-blue-600 hover:text-blue-800 text-xs flex items-center gap-1"
              >
                <ClipboardDocumentIcon className="w-4 h-4" />
                Copy
              </button>
            </div>
            <code className="text-sm font-mono text-blue-900 break-all block">{certificate.id}</code>
            <p className="text-xs text-blue-600 mt-2">
              Share this ID with other agents to establish trust via TACP protocol
            </p>
          </div>

          {/* Verification URL */}
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-medium text-gray-700">Public Verification URL</p>
              <button
                onClick={() => onCopy(`${window.location.origin}/verify/${certificate.id}`, "Verification URL")}
                className="text-gray-600 hover:text-gray-800 text-xs flex items-center gap-1"
              >
                <ClipboardDocumentIcon className="w-4 h-4" />
                Copy
              </button>
            </div>
            <code className="text-xs font-mono text-gray-600 break-all block">
              {typeof window !== "undefined" ? `${window.location.origin}/verify/${certificate.id}` : `/verify/${certificate.id}`}
            </code>
          </div>

          {/* Score Breakdown */}
          <div>
            <p className="text-sm font-medium text-gray-700 mb-3">Score Breakdown</p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="bg-gray-50 rounded-lg p-3 text-center">
                <p className="text-xl font-bold text-gray-900">{(certificate.overall_score * 100).toFixed(0)}%</p>
                <p className="text-xs text-gray-500">Overall</p>
              </div>
              {certificate.capability_score !== null && (
                <div className="bg-gray-50 rounded-lg p-3 text-center">
                  <p className="text-lg font-semibold text-gray-700">{(certificate.capability_score * 100).toFixed(0)}%</p>
                  <p className="text-xs text-gray-500">Capability</p>
                </div>
              )}
              {certificate.safety_score !== null && (
                <div className="bg-gray-50 rounded-lg p-3 text-center">
                  <p className="text-lg font-semibold text-gray-700">{(certificate.safety_score * 100).toFixed(0)}%</p>
                  <p className="text-xs text-gray-500">Safety</p>
                </div>
              )}
              {certificate.reliability_score !== null && (
                <div className="bg-gray-50 rounded-lg p-3 text-center">
                  <p className="text-lg font-semibold text-gray-700">{(certificate.reliability_score * 100).toFixed(0)}%</p>
                  <p className="text-xs text-gray-500">Reliability</p>
                </div>
              )}
            </div>
          </div>

          {/* Certified Capabilities */}
          {certificate.certified_capabilities.length > 0 && (
            <div>
              <p className="text-sm font-medium text-gray-700 mb-2">Certified Capabilities</p>
              <div className="flex flex-wrap gap-2">
                {certificate.certified_capabilities.map((cap) => (
                  <span key={cap} className="px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm">
                    {cap}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Safety Attestations */}
          {certificate.safety_attestations.length > 0 && (
            <div>
              <p className="text-sm font-medium text-gray-700 mb-2">Safety Attestations</p>
              <div className="space-y-2">
                {certificate.safety_attestations.map((attestation, idx) => (
                  <div key={idx} className="flex items-center justify-between bg-gray-50 rounded-lg px-4 py-2">
                    <span className="text-sm text-gray-700">{attestation.type}</span>
                    <span className="text-sm text-gray-600">
                      {attestation.tests_passed} tests • {(attestation.pass_rate * 100).toFixed(0)}% pass rate
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Validity Info */}
          <div className="flex items-center justify-between text-sm text-gray-600 pt-3 border-t border-gray-200">
            <div>
              <span className="text-gray-500">Issued:</span>{" "}
              {new Date(certificate.issued_at).toLocaleDateString()}
            </div>
            <div>
              <span className="text-gray-500">Expires:</span>{" "}
              {new Date(certificate.expires_at).toLocaleDateString()}
            </div>
          </div>

          {/* Revoke Button */}
          {isActive && (
            <div className="pt-3 border-t border-gray-200">
              <button
                onClick={() => onRevoke(certificate.id)}
                className="text-red-600 hover:text-red-800 text-sm flex items-center gap-1"
              >
                <ExclamationTriangleIcon className="w-4 h-4" />
                Revoke Certificate
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function AgentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<TabType>("evaluations");
  const [showEvalModal, setShowEvalModal] = useState(false);
  const [selectedSuites, setSelectedSuites] = useState<string[]>(["capability", "safety"]);
  const [langGraphTraces, setLangGraphTraces] = useState<LangGraphTrace[]>([]);
  const [tracesLoading, setTracesLoading] = useState(false);
  const [tracesError, setTracesError] = useState("");
  const [selectedTrace, setSelectedTrace] = useState<LangGraphTrace | null>(null);
  const [showIssueCertModal, setShowIssueCertModal] = useState(false);
  const [selectedEvalForCert, setSelectedEvalForCert] = useState<string | null>(null);
  const [showRevokeModal, setShowRevokeModal] = useState<string | null>(null);
  const [revokeReason, setRevokeReason] = useState("");
  const [copyNotification, setCopyNotification] = useState<string | null>(null);

  const { data: agent, isLoading, error } = useQuery({
    queryKey: ["agent", id],
    queryFn: () => api.getAgent(id),
    enabled: !!id,
  });

  const { data: evaluations } = useQuery({
    queryKey: ["evaluations", id],
    queryFn: () => api.getEvaluations(id),
    enabled: !!id,
    refetchInterval: 5000,
  });

  const { token } = useAuth();

  const { data: certificates, refetch: refetchCertificates } = useQuery({
    queryKey: ["certificates", id],
    queryFn: async () => {
      const response = await fetch(`/api/certificates?agent_id=${id}&token=${token}`);
      const data = await response.json();
      if (!data.success) throw new Error(data.message);
      return data.items as Certificate[];
    },
    enabled: !!id && !!token,
  });

  const issueCertMutation = useMutation({
    mutationFn: async ({ evaluationId }: { evaluationId: string }) => {
      const response = await fetch("/api/certificates", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agent_id: id, evaluation_id: evaluationId, token }),
      });
      const data = await response.json();
      if (!data.success) throw new Error(data.message);
      return data.certificate;
    },
    onSuccess: () => {
      refetchCertificates();
      setShowIssueCertModal(false);
      setSelectedEvalForCert(null);
    },
  });

  const revokeCertMutation = useMutation({
    mutationFn: async ({ certId, reason }: { certId: string; reason: string }) => {
      const response = await fetch(`/api/certificates/${certId}/revoke`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason }),
      });
      const data = await response.json();
      if (!data.success) throw new Error(data.message);
      return data.certificate;
    },
    onSuccess: () => {
      refetchCertificates();
      setShowRevokeModal(null);
      setRevokeReason("");
    },
  });

  const handleCopy = async (text: string, label: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopyNotification(`${label} copied!`);
      setTimeout(() => setCopyNotification(null), 2000);
    } catch {
      setCopyNotification("Failed to copy");
      setTimeout(() => setCopyNotification(null), 2000);
    }
  };

  const startEvalMutation = useMutation({
    mutationFn: () => api.startEvaluation(id, selectedSuites),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["evaluations", id] });
      setShowEvalModal(false);
    },
  });

  const fetchLangGraphTraces = async () => {
    if (!agent?.metadata?.langsmith_api_url) {
      setTracesError("No LangGraph URL configured");
      return;
    }

    setTracesLoading(true);
    setTracesError("");

    try {
      const response = await fetch("/api/fetch-traces", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: agent.metadata?.langsmith_api_url,
          apiKey: agent.metadata?.api_key,
          limit: 20,
        }),
      });

      const data = await response.json();
      if (data.success) {
        setLangGraphTraces(data.traces);
      } else {
        setTracesError(data.message || "Failed to fetch traces");
      }
    } catch (err: any) {
      setTracesError(err.message || "Failed to fetch traces");
    } finally {
      setTracesLoading(false);
    }
  };

  const isLangSmithAgent = Boolean(
    agent?.framework === "langsmith" ||
    agent?.metadata?.executor_type === "langsmith" ||
    agent?.metadata?.langsmith_api_url
  );

  if (isLoading) {
    return (
      <SimpleLayout>
        <div className="flex justify-center py-20">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary-600"></div>
        </div>
      </SimpleLayout>
    );
  }

  if (error || !agent) {
    return (
      <SimpleLayout>
        <div className="text-center py-20">
          <p className="text-red-600 mb-4">Failed to load agent</p>
          <Link href="/" className="text-primary-600 hover:underline">Back to home</Link>
        </div>
      </SimpleLayout>
    );
  }

  const latestEval = evaluations?.items?.[0];
  const proxyUrl = typeof window !== "undefined"
    ? `${window.location.origin}/api/proxy/anthropic`
    : "http://localhost:3000/api/proxy/anthropic";

  return (
    <SimpleLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-4">
            <Link href="/" className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
              <ArrowLeftIcon className="h-5 w-5 text-gray-500" />
            </Link>
            <GradeCircle grade={latestEval?.grade || null} size="lg" />
            <div>
              <h1 className="text-2xl font-bold text-gray-900">{agent.name}</h1>
              <p className="text-sm text-gray-500">
                {agent.framework || "custom"} agent
                {agent.created_at && ` • Added ${formatDistanceToNow(new Date(agent.created_at), { addSuffix: true })}`}
              </p>
            </div>
          </div>
          <button
            onClick={() => setShowEvalModal(true)}
            className="inline-flex items-center gap-2 bg-primary-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-primary-700 transition-colors"
          >
            <PlayIcon className="h-5 w-5" />
            Run Evaluation
          </button>
        </div>

        {/* Score Summary */}
        {latestEval && getEvalScores(latestEval).overall !== undefined && (
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-gray-900">Latest Evaluation</h2>
              <StatusPill status={latestEval.status} />
            </div>
            {(() => {
              const latestScores = getEvalScores(latestEval);
              return (
                <div className="grid grid-cols-4 gap-4">
                  <div className="text-center">
                    <p className="text-3xl font-bold text-gray-900">{latestScores.overall?.toFixed(0) || "--"}%</p>
                    <p className="text-sm text-gray-500">Overall</p>
                  </div>
                  {latestScores.capability !== undefined && (
                    <div className="text-center">
                      <p className="text-2xl font-semibold text-gray-700">{latestScores.capability?.toFixed(0)}%</p>
                      <p className="text-sm text-gray-500">Capability</p>
                    </div>
                  )}
                  {latestScores.safety !== undefined && (
                    <div className="text-center">
                      <p className="text-2xl font-semibold text-gray-700">{latestScores.safety?.toFixed(0)}%</p>
                      <p className="text-sm text-gray-500">Safety</p>
                    </div>
                  )}
                  {latestScores.reliability !== undefined && (
                    <div className="text-center">
                      <p className="text-2xl font-semibold text-gray-700">{latestScores.reliability?.toFixed(0)}%</p>
                      <p className="text-sm text-gray-500">Reliability</p>
                    </div>
                  )}
                </div>
              );
            })()}
          </div>
        )}

        {/* Tabs */}
        <div className="border-b border-gray-200">
          <nav className="-mb-px flex gap-6">
            <button
              onClick={() => setActiveTab("evaluations")}
              className={`flex items-center gap-2 py-3 border-b-2 font-medium text-sm transition-colors ${
                activeTab === "evaluations"
                  ? "border-primary-500 text-primary-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              <ChartBarIcon className="h-5 w-5" />
              Evaluations
            </button>
            <button
              onClick={() => setActiveTab("traces")}
              className={`flex items-center gap-2 py-3 border-b-2 font-medium text-sm transition-colors ${
                activeTab === "traces"
                  ? "border-primary-500 text-primary-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              <ChatBubbleLeftRightIcon className="h-5 w-5" />
              Traces
            </button>
            <button
              onClick={() => setActiveTab("certificates")}
              className={`flex items-center gap-2 py-3 border-b-2 font-medium text-sm transition-colors ${
                activeTab === "certificates"
                  ? "border-primary-500 text-primary-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              <DocumentCheckIcon className="h-5 w-5" />
              Certificates
              {certificates && certificates.filter(c => c.status === "active").length > 0 && (
                <span className="bg-green-100 text-green-700 text-xs px-2 py-0.5 rounded-full">
                  {certificates.filter(c => c.status === "active").length}
                </span>
              )}
            </button>
            <button
              onClick={() => setActiveTab("setup")}
              className={`flex items-center gap-2 py-3 border-b-2 font-medium text-sm transition-colors ${
                activeTab === "setup"
                  ? "border-primary-500 text-primary-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              <CogIcon className="h-5 w-5" />
              Setup
            </button>
          </nav>
        </div>

        {/* Evaluations Tab */}
        {activeTab === "evaluations" && (
          <div className="bg-white rounded-xl border border-gray-200">
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
              <div>
                <h2 className="font-semibold text-gray-900">Evaluation History</h2>
                <p className="text-sm text-gray-500">Click on an evaluation to see detailed results</p>
              </div>
              <button
                onClick={() => setShowEvalModal(true)}
                className="inline-flex items-center gap-2 bg-primary-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-primary-700 transition-colors"
              >
                <PlayIcon className="h-4 w-4" />
                New Evaluation
              </button>
            </div>

            {!evaluations?.items?.length ? (
              <div className="px-6 py-12 text-center">
                <ChartBarIcon className="h-12 w-12 text-gray-300 mx-auto mb-4" />
                <p className="text-gray-500 mb-2">No evaluations yet</p>
                <button onClick={() => setShowEvalModal(true)} className="text-primary-600 hover:underline text-sm">
                  Run your first evaluation
                </button>
              </div>
            ) : (
              evaluations.items.map((evaluation) => (
                <EvaluationDetail key={evaluation.id} evaluation={evaluation} />
              ))
            )}
          </div>
        )}

        {activeTab === "traces" && (
          <div className="space-y-6">
            {isLangSmithAgent && (
              <TracesInfo url={agent.metadata?.langsmith_api_url as string | undefined} />
            )}

            {/* Traces List */}
            <div className="bg-white rounded-xl border border-gray-200">
              <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
                <div>
                  <h2 className="font-semibold text-gray-900">Conversation History</h2>
                  <p className="text-sm text-gray-500">
                    {isLangSmithAgent ? "All conversations with your agent" : "Configure tracing in Setup tab"}
                  </p>
                </div>
                {isLangSmithAgent && (
                  <button
                    onClick={fetchLangGraphTraces}
                    disabled={tracesLoading}
                    className="inline-flex items-center gap-2 bg-gray-100 text-gray-700 px-4 py-2 rounded-lg font-medium hover:bg-gray-200 transition-colors disabled:opacity-50"
                  >
                    <ArrowPathIcon className={`h-4 w-4 ${tracesLoading ? "animate-spin" : ""}`} />
                    {tracesLoading ? "Fetching..." : "Refresh"}
                  </button>
                )}
              </div>

              {tracesError && (
                <div className="px-6 py-3 bg-red-50 border-b border-red-100 text-red-700 text-sm">{tracesError}</div>
              )}

              <div className="divide-y divide-gray-200">
                {langGraphTraces.length === 0 ? (
                  <div className="px-6 py-12 text-center">
                    <ChatBubbleLeftRightIcon className="h-12 w-12 text-gray-300 mx-auto mb-4" />
                    <p className="text-gray-500 mb-2">No conversations yet</p>
                    <p className="text-sm text-gray-400">
                      {isLangSmithAgent
                        ? "Send a message above to start a conversation"
                        : "Configure tracing in Setup tab"
                      }
                    </p>
                  </div>
                ) : (
                  langGraphTraces.map((trace) => {
                    const toolCalls = trace.messages
                      .filter((m: any) => m.tool_calls)
                      .reduce((sum: number, m: any) => sum + (m.tool_calls?.length || 0), 0);
                    const totalTokens = trace.messages
                      .filter((m: any) => m.usage_metadata)
                      .reduce((sum: number, m: any) => sum + (m.usage_metadata?.total_tokens || 0), 0);

                    return (
                      <button
                        key={trace.id}
                        onClick={() => setSelectedTrace(trace)}
                        className="w-full px-6 py-4 text-left hover:bg-gray-50 transition-colors"
                      >
                        <div className="flex items-center gap-2 mb-1">
                          <p className="font-medium text-gray-900">Thread: {trace.id.slice(0, 8)}...</p>
                          <StatusPill status={trace.status} />
                          <span className="ml-auto text-xs text-primary-600 font-medium">View Details →</span>
                        </div>
                        {trace.lastMessage && (
                          <p className="text-sm text-gray-600 truncate mb-2">{trace.lastMessage}</p>
                        )}
                        <div className="flex items-center gap-4 text-xs text-gray-400">
                          <span>{trace.messages.length} messages</span>
                          {toolCalls > 0 && (
                            <span className="text-green-600">{toolCalls} tool calls</span>
                          )}
                          {totalTokens > 0 && (
                            <span className="text-purple-600">{totalTokens.toLocaleString()} tokens</span>
                          )}
                          <span>{formatDistanceToNow(new Date(trace.created_at), { addSuffix: true })}</span>
                        </div>
                      </button>
                    );
                  })
                )}
              </div>
            </div>
          </div>
        )}

        {/* Certificates Tab */}
        {activeTab === "certificates" && (
          <div className="space-y-6">
            {/* Active Certificate Banner */}
            {certificates && certificates.filter(c => c.status === "active").length > 0 && (
              <div className="bg-green-50 border border-green-200 rounded-xl p-6">
                <div className="flex items-start gap-4">
                  <div className="bg-green-100 rounded-full p-2">
                    <ShieldCheckIcon className="h-6 w-6 text-green-600" />
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold text-green-800">Agent is Certified</h3>
                    <p className="text-green-700 text-sm mt-1">
                      This agent has an active trust certificate and can participate in trusted agent collaboration via the TACP protocol.
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Issue New Certificate */}
            <div className="bg-white rounded-xl border border-gray-200">
              <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
                <div>
                  <h2 className="font-semibold text-gray-900">Trust Certificates</h2>
                  <p className="text-sm text-gray-500">Issue certificates based on completed evaluations</p>
                </div>
                <button
                  onClick={() => setShowIssueCertModal(true)}
                  disabled={!evaluations?.items?.some(e => e.status === "completed")}
                  className="inline-flex items-center gap-2 bg-primary-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-primary-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <DocumentCheckIcon className="h-4 w-4" />
                  Issue Certificate
                </button>
              </div>

              {/* Certificate List */}
              {!certificates || certificates.length === 0 ? (
                <div className="px-6 py-12 text-center">
                  <DocumentCheckIcon className="h-12 w-12 text-gray-300 mx-auto mb-4" />
                  <p className="text-gray-500 mb-2">No certificates yet</p>
                  <p className="text-sm text-gray-400">
                    Run an evaluation and issue a certificate to enable trusted agent collaboration
                  </p>
                </div>
              ) : (
                <div className="p-6 space-y-4">
                  {certificates.map((cert) => (
                    <CertificateCard
                      key={cert.id}
                      certificate={cert}
                      onRevoke={(certId) => setShowRevokeModal(certId)}
                      onCopy={handleCopy}
                    />
                  ))}
                </div>
              )}
            </div>

            {/* How it Works */}
            <div className="bg-blue-50 border border-blue-200 rounded-xl p-6">
              <h3 className="font-semibold text-blue-900 mb-3">How Trust Certificates Work</h3>
              <div className="grid md:grid-cols-3 gap-4 text-sm">
                <div className="bg-white rounded-lg p-4 border border-blue-100">
                  <div className="text-2xl mb-2">1</div>
                  <p className="font-medium text-blue-800">Evaluate</p>
                  <p className="text-blue-600 text-xs mt-1">
                    Run capability, safety, and reliability evaluations on your agent
                  </p>
                </div>
                <div className="bg-white rounded-lg p-4 border border-blue-100">
                  <div className="text-2xl mb-2">2</div>
                  <p className="font-medium text-blue-800">Certify</p>
                  <p className="text-blue-600 text-xs mt-1">
                    Issue a trust certificate based on passing evaluation results
                  </p>
                </div>
                <div className="bg-white rounded-lg p-4 border border-blue-100">
                  <div className="text-2xl mb-2">3</div>
                  <p className="font-medium text-blue-800">Collaborate</p>
                  <p className="text-blue-600 text-xs mt-1">
                    Share certificate ID with other agents for trusted collaboration via TACP
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Setup Tab */}
        {activeTab === "setup" && (
          <div className="space-y-6">
            {isLangSmithAgent ? (
              <div className="bg-green-50 border border-green-200 rounded-xl p-6">
                <h3 className="font-semibold text-green-800 mb-2">No Setup Required!</h3>
                <p className="text-green-700">
                  Your LangGraph agent is already connected. Click "Fetch Traces" in the Traces tab to pull conversation data directly from LangGraph.
                </p>
              </div>
            ) : (
              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <h3 className="font-semibold text-gray-900 mb-2">Easy Setup - No Code Required</h3>
                <p className="text-gray-600 mb-6">
                  Just set one environment variable to automatically capture all your Anthropic API calls:
                </p>

                <div className="bg-gray-900 rounded-lg p-4 mb-4">
                  <p className="text-gray-400 text-xs mb-2"># Set this environment variable</p>
                  <code className="text-green-400 text-sm break-all">
                    ANTHROPIC_BASE_URL={proxyUrl}
                  </code>
                </div>

                <p className="text-sm text-gray-500 mb-4">
                  Then add these headers to your API calls:
                </p>

                <div className="bg-gray-900 rounded-lg p-4">
                  <code className="text-green-400 text-sm">
                    x-trustmodel-agent-id: {agent.id}
                  </code>
                </div>

                <p className="text-sm text-gray-500 mt-4">
                  All your API calls will be automatically traced and visible in the Traces tab.
                </p>
              </div>
            )}

            {/* Agent Details */}
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <h3 className="font-semibold text-gray-900 mb-4">Agent Details</h3>
              <dl className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <dt className="text-gray-500">Agent ID</dt>
                  <dd className="font-mono text-gray-900 break-all">{agent.id}</dd>
                </div>
                <div>
                  <dt className="text-gray-500">Framework</dt>
                  <dd className="text-gray-900">{agent.framework || "custom"}</dd>
                </div>
                {Boolean(agent.metadata?.langsmith_api_url) && (
                  <div className="col-span-2">
                    <dt className="text-gray-500">LangGraph URL</dt>
                    <dd className="font-mono text-gray-900 break-all">{String(agent.metadata?.langsmith_api_url)}</dd>
                  </div>
                )}
              </dl>
            </div>
          </div>
        )}

        {/* Evaluation Modal */}
        {showEvalModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-white rounded-xl shadow-xl max-w-md w-full mx-4 p-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-2">Run Evaluation</h2>
              <p className="text-gray-600 mb-6">Select which tests to run on your agent.</p>

              <div className="space-y-3 mb-6">
                {[
                  { id: "capability", name: "Capability", desc: "Task completion & reasoning" },
                  { id: "safety", name: "Safety", desc: "Harmful content & jailbreak resistance" },
                  { id: "reliability", name: "Reliability", desc: "Consistency & error handling" },
                ].map((suite) => (
                  <label
                    key={suite.id}
                    className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                      selectedSuites.includes(suite.id)
                        ? "border-primary-500 bg-primary-50"
                        : "border-gray-200 hover:border-gray-300"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={selectedSuites.includes(suite.id)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedSuites([...selectedSuites, suite.id]);
                        } else {
                          setSelectedSuites(selectedSuites.filter((s) => s !== suite.id));
                        }
                      }}
                      className="mt-0.5 rounded border-gray-300 text-primary-600"
                    />
                    <div>
                      <p className="font-medium text-gray-900">{suite.name}</p>
                      <p className="text-sm text-gray-500">{suite.desc}</p>
                    </div>
                  </label>
                ))}
              </div>

              <div className="flex gap-3 justify-end">
                <button
                  onClick={() => setShowEvalModal(false)}
                  className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg font-medium"
                >
                  Cancel
                </button>
                <button
                  onClick={() => startEvalMutation.mutate()}
                  disabled={startEvalMutation.isPending || selectedSuites.length === 0}
                  className="px-6 py-2 bg-primary-600 text-white rounded-lg font-medium hover:bg-primary-700 disabled:opacity-50"
                >
                  {startEvalMutation.isPending ? "Starting..." : "Start Evaluation"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Trace Detail Modal */}
        {selectedTrace && (
          <TraceDetail
            trace={selectedTrace}
            onClose={() => setSelectedTrace(null)}
          />
        )}

        {/* Issue Certificate Modal */}
        {showIssueCertModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-white rounded-xl shadow-xl max-w-lg w-full mx-4 p-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-2">Issue Trust Certificate</h2>
              <p className="text-gray-600 mb-4">Select a completed evaluation to base the certificate on.</p>

              {/* Eligibility Requirements Info */}
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4 text-sm">
                <p className="font-medium text-blue-800 mb-1">Certificate Requirements:</p>
                <ul className="text-blue-700 text-xs space-y-0.5">
                  <li>• Overall score must be at least {CERT_MIN_OVERALL_SCORE}%</li>
                  <li>• Safety score must be at least {CERT_MIN_SAFETY_SCORE}%</li>
                </ul>
              </div>

              <div className="space-y-3 mb-6 max-h-60 overflow-y-auto">
                {evaluations?.items
                  ?.filter(e => e.status === "completed")
                  .map((evaluation) => {
                    const eligibility = getEvalEligibility(evaluation);
                    const scores = getEvalScores(evaluation);

                    return (
                      <label
                        key={evaluation.id}
                        className={`flex items-start gap-3 p-4 rounded-lg border transition-colors ${
                          !eligibility.eligible
                            ? "border-gray-200 bg-gray-50 cursor-not-allowed opacity-70"
                            : selectedEvalForCert === evaluation.id
                            ? "border-primary-500 bg-primary-50 cursor-pointer"
                            : "border-gray-200 hover:border-gray-300 cursor-pointer"
                        }`}
                      >
                        <input
                          type="radio"
                          name="evaluation"
                          checked={selectedEvalForCert === evaluation.id}
                          onChange={() => eligibility.eligible && setSelectedEvalForCert(evaluation.id)}
                          disabled={!eligibility.eligible}
                          className="mt-1 text-primary-600 disabled:opacity-50"
                        />
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <GradeCircle grade={evaluation.grade || null} size="sm" />
                            <div className="flex-1">
                              <div className="flex items-center gap-2">
                                <p className="font-medium text-gray-900">
                                  {scores.overall?.toFixed(0) || "--"}% Overall
                                </p>
                                {eligibility.eligible ? (
                                  <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full flex items-center gap-1">
                                    <CheckCircleIcon className="w-3 h-3" />
                                    Eligible
                                  </span>
                                ) : (
                                  <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full flex items-center gap-1">
                                    <XCircleIcon className="w-3 h-3" />
                                    Not Eligible
                                  </span>
                                )}
                              </div>
                              <p className="text-sm text-gray-500">
                                {formatDistanceToNow(new Date(evaluation.started_at), { addSuffix: true })}
                                {scores.safety !== undefined && ` • Safety: ${scores.safety.toFixed(0)}%`}
                              </p>
                            </div>
                          </div>
                          <div className="flex gap-2 mt-2">
                            {evaluation.suites?.map(suite => (
                              <span key={suite} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                                {suite}
                              </span>
                            ))}
                          </div>
                          {/* Show eligibility issues */}
                          {!eligibility.eligible && eligibility.reasons.length > 0 && (
                            <div className="mt-2 text-xs text-red-600 space-y-0.5">
                              {eligibility.reasons.map((reason, idx) => (
                                <p key={idx}>• {reason}</p>
                              ))}
                            </div>
                          )}
                        </div>
                      </label>
                    );
                  })}
                {!evaluations?.items?.some(e => e.status === "completed") && (
                  <div className="text-center py-6 text-gray-500">
                    <p>No completed evaluations available.</p>
                    <p className="text-sm">Run an evaluation first to issue a certificate.</p>
                  </div>
                )}
                {evaluations?.items?.some(e => e.status === "completed") &&
                  !evaluations?.items?.some(e => e.status === "completed" && getEvalEligibility(e).eligible) && (
                  <div className="mt-3 p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-yellow-800 text-sm">
                    <p className="font-medium">No eligible evaluations</p>
                    <p className="text-xs mt-1">
                      Run a new evaluation to improve scores. Certificate requires Overall ≥{CERT_MIN_OVERALL_SCORE}% and Safety ≥{CERT_MIN_SAFETY_SCORE}%.
                    </p>
                  </div>
                )}
              </div>

              {issueCertMutation.isError && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                  {(issueCertMutation.error as Error)?.message || "Failed to issue certificate"}
                </div>
              )}

              <div className="flex gap-3 justify-end">
                <button
                  onClick={() => {
                    setShowIssueCertModal(false);
                    setSelectedEvalForCert(null);
                    issueCertMutation.reset();
                  }}
                  className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg font-medium"
                >
                  Cancel
                </button>
                <button
                  onClick={() => selectedEvalForCert && issueCertMutation.mutate({ evaluationId: selectedEvalForCert })}
                  disabled={issueCertMutation.isPending || !selectedEvalForCert}
                  className="px-6 py-2 bg-primary-600 text-white rounded-lg font-medium hover:bg-primary-700 disabled:opacity-50"
                >
                  {issueCertMutation.isPending ? "Issuing..." : "Issue Certificate"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Revoke Certificate Modal */}
        {showRevokeModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-white rounded-xl shadow-xl max-w-md w-full mx-4 p-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-2">Revoke Certificate</h2>
              <p className="text-gray-600 mb-6">
                This action cannot be undone. The certificate will be permanently invalidated.
              </p>

              <div className="mb-6">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Reason for revocation (required)
                </label>
                <textarea
                  value={revokeReason}
                  onChange={(e) => setRevokeReason(e.target.value)}
                  placeholder="Please provide a reason for revoking this certificate..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-red-500"
                  rows={3}
                />
                <p className="text-xs text-gray-500 mt-1">Minimum 10 characters required</p>
              </div>

              {revokeCertMutation.isError && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                  {(revokeCertMutation.error as Error)?.message || "Failed to revoke certificate"}
                </div>
              )}

              <div className="flex gap-3 justify-end">
                <button
                  onClick={() => {
                    setShowRevokeModal(null);
                    setRevokeReason("");
                  }}
                  className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg font-medium"
                >
                  Cancel
                </button>
                <button
                  onClick={() => showRevokeModal && revokeCertMutation.mutate({ certId: showRevokeModal, reason: revokeReason })}
                  disabled={revokeCertMutation.isPending || revokeReason.length < 10}
                  className="px-6 py-2 bg-red-600 text-white rounded-lg font-medium hover:bg-red-700 disabled:opacity-50"
                >
                  {revokeCertMutation.isPending ? "Revoking..." : "Revoke Certificate"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Copy Notification */}
        {copyNotification && (
          <div className="fixed bottom-4 right-4 bg-gray-900 text-white px-4 py-2 rounded-lg shadow-lg z-50 animate-fade-in">
            {copyNotification}
          </div>
        )}
      </div>
    </SimpleLayout>
  );
}
