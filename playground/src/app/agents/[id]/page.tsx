"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";
import {
  ArrowLeftIcon,
  PlayIcon,
  ClipboardIcon,
  CheckIcon,
  CogIcon,
  ChartBarIcon,
  DocumentTextIcon,
  ShieldCheckIcon,
} from "@heroicons/react/24/outline";
import Link from "next/link";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { api } from "@/lib/api";
import { GradeBadge } from "@/components/ui/GradeBadge";
import { StatusBadge } from "@/components/ui/StatusBadge";

type TabType = "overview" | "setup" | "traces" | "evaluations";

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      onClick={handleCopy}
      className="absolute top-2 right-2 p-2 rounded-lg bg-gray-700 hover:bg-gray-600 transition-colors"
      title="Copy to clipboard"
    >
      {copied ? (
        <CheckIcon className="h-4 w-4 text-green-400" />
      ) : (
        <ClipboardIcon className="h-4 w-4 text-gray-300" />
      )}
    </button>
  );
}

function CodeBlock({ code, language = "python" }: { code: string; language?: string }) {
  return (
    <div className="relative">
      <pre className="bg-gray-900 text-gray-100 rounded-lg p-4 text-sm overflow-x-auto">
        <code>{code}</code>
      </pre>
      <CopyButton text={code} />
    </div>
  );
}

export default function AgentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<TabType>("overview");
  const [showEvalModal, setShowEvalModal] = useState(false);
  const [selectedSuites, setSelectedSuites] = useState<string[]>([
    "capability",
    "safety",
    "reliability",
    "communication",
  ]);

  const { data: agent, isLoading, error } = useQuery({
    queryKey: ["agent", id],
    queryFn: () => api.getAgent(id),
    enabled: !!id,
  });

  const { data: evaluations } = useQuery({
    queryKey: ["evaluations", id],
    queryFn: () => api.getEvaluations(id),
    enabled: !!id,
  });

  const { data: traces } = useQuery({
    queryKey: ["traces", id],
    queryFn: () => api.getTraces(id),
    enabled: !!id && activeTab === "traces",
  });

  const startEvalMutation = useMutation({
    mutationFn: () => api.startEvaluation(id, selectedSuites),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["evaluations", id] });
      setShowEvalModal(false);
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

  if (error || !agent) {
    return (
      <DashboardLayout>
        <div className="text-center py-12">
          <p className="text-red-600 mb-4">Failed to load agent</p>
          <Link href="/agents" className="text-primary-600 hover:underline">
            Back to agents
          </Link>
        </div>
      </DashboardLayout>
    );
  }

  const tabs = [
    { id: "overview" as TabType, label: "Overview", icon: ChartBarIcon },
    { id: "setup" as TabType, label: "Setup", icon: CogIcon },
    { id: "traces" as TabType, label: "Traces", icon: DocumentTextIcon },
    { id: "evaluations" as TabType, label: "Evaluations", icon: ShieldCheckIcon },
  ];

  // Get the user's token from localStorage for display
  const token = typeof window !== "undefined" ? localStorage.getItem("trustmodel_token") : "";

  // Generate integration code based on framework
  const getIntegrationCode = () => {
    const framework = agent.framework || "anthropic-api";
    const serverUrl = typeof window !== "undefined" ? window.location.origin.replace("3000", "8000") : "http://localhost:8000";

    switch (framework) {
      case "anthropic-api":
        return {
          title: "Anthropic API Integration",
          description: "Add automatic tracing to your Anthropic API calls with just one line of code.",
          steps: [
            {
              title: "1. Install the SDK",
              code: "pip install trustmodel",
            },
            {
              title: "2. Add instrumentation to your code",
              code: `from trustmodel import instrument
from anthropic import Anthropic

# Initialize TrustModel tracing
instrument(
    agent_id="${agent.id}",
    server_url="${serverUrl}",
    api_key="${token || "your-trustmodel-api-key"}"
)

# Your existing Anthropic code works as normal
client = Anthropic()
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello!"}]
)

# All API calls are automatically traced!`,
            },
          ],
        };

      case "openai":
        return {
          title: "OpenAI API Integration",
          description: "Add automatic tracing to your OpenAI API calls.",
          steps: [
            {
              title: "1. Install the SDK",
              code: "pip install trustmodel",
            },
            {
              title: "2. Add instrumentation to your code",
              code: `from trustmodel import instrument
from openai import OpenAI

# Initialize TrustModel tracing
instrument(
    agent_id="${agent.id}",
    server_url="${serverUrl}",
    api_key="${token || "your-trustmodel-api-key"}"
)

# Your existing OpenAI code works as normal
client = OpenAI()
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello!"}]
)

# All API calls are automatically traced!`,
            },
          ],
        };

      case "claude-code":
        return {
          title: "Claude Code (Local Proxy)",
          description: "Run Claude Code through a local proxy to capture all traces.",
          steps: [
            {
              title: "1. Install the TrustModel CLI",
              code: "pip install trustmodel",
            },
            {
              title: "2. Start the proxy",
              code: `# Start the TrustModel proxy
trustmodel \\
  --server ${serverUrl} \\
  --api-key ${token || "your-trustmodel-api-key"} \\
  proxy start \\
  --port 8080 \\
  --agent ${agent.id}`,
            },
            {
              title: "3. Configure Claude Code to use the proxy",
              code: `# In a new terminal, set these environment variables
export ANTHROPIC_BASE_URL=http://localhost:8080/anthropic

# Then run Claude Code normally
claude`,
            },
          ],
        };

      case "langchain":
        return {
          title: "LangChain Integration",
          description: "Add tracing to your LangChain applications.",
          steps: [
            {
              title: "1. Install the SDK",
              code: "pip install trustmodel",
            },
            {
              title: "2. Add instrumentation",
              code: `from trustmodel import instrument
from langchain_anthropic import ChatAnthropic
from langchain.schema import HumanMessage

# Initialize TrustModel tracing (auto-patches LangChain)
instrument(
    agent_id="${agent.id}",
    server_url="${serverUrl}",
    api_key="${token || "your-trustmodel-api-key"}"
)

# Your LangChain code works as normal
chat = ChatAnthropic(model="claude-sonnet-4-20250514")
response = chat.invoke([HumanMessage(content="Hello!")])

# All LLM calls are automatically traced!`,
            },
          ],
        };

      default:
        return {
          title: "Custom Agent Integration",
          description: "Send traces directly to the TrustModel API.",
          steps: [
            {
              title: "1. Send traces via API",
              code: `# POST ${serverUrl}/v1/traces
curl -X POST ${serverUrl}/v1/traces \\
  -H "Authorization: Bearer ${token || "your-trustmodel-api-key"}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "agent_id": "${agent.id}",
    "traces": [{
      "trace_id": "unique-trace-id",
      "name": "my-agent-action",
      "started_at": "2024-01-01T00:00:00Z",
      "ended_at": "2024-01-01T00:00:01Z",
      "spans": [{
        "span_id": "span-1",
        "name": "llm_call",
        "span_type": "llm_call",
        "started_at": "2024-01-01T00:00:00Z",
        "ended_at": "2024-01-01T00:00:01Z",
        "attributes": {
          "model": "your-model",
          "input_tokens": 100,
          "output_tokens": 50
        }
      }]
    }]
  }'`,
            },
          ],
        };
    }
  };

  const integration = getIntegrationCode();

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link
              href="/agents"
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <ArrowLeftIcon className="h-5 w-5 text-gray-500" />
            </Link>
            <div className="flex items-center gap-3">
              {agent.stats?.latest_certificate_grade ? (
                <GradeBadge grade={agent.stats.latest_certificate_grade} size="lg" />
              ) : (
                <div className="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center">
                  <span className="text-gray-400 text-lg">--</span>
                </div>
              )}
              <div>
                <h1 className="text-2xl font-bold text-gray-900">{agent.name}</h1>
                <p className="text-sm text-gray-500">
                  {agent.agent_type} • {agent.framework || "custom"} •{" "}
                  {formatDistanceToNow(new Date(agent.created_at), { addSuffix: true })}
                </p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowEvalModal(true)}
              className="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
            >
              <PlayIcon className="h-5 w-5" />
              Run Evaluation
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="border-b border-gray-200">
          <nav className="-mb-px flex space-x-8">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                    activeTab === tab.id
                      ? "border-primary-500 text-primary-600"
                      : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
                  }`}
                >
                  <Icon className="h-5 w-5" />
                  {tab.label}
                </button>
              );
            })}
          </nav>
        </div>

        {/* Tab Content */}
        {activeTab === "overview" && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-6">
              {/* Quick Stats */}
              <div className="grid grid-cols-3 gap-4">
                <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                  <p className="text-sm text-gray-500">Total Traces</p>
                  <p className="text-3xl font-bold text-gray-900 mt-1">
                    {agent.stats?.total_traces || 0}
                  </p>
                </div>
                <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                  <p className="text-sm text-gray-500">Evaluations</p>
                  <p className="text-3xl font-bold text-gray-900 mt-1">
                    {agent.stats?.total_evaluations || 0}
                  </p>
                </div>
                <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                  <p className="text-sm text-gray-500">Current Grade</p>
                  <div className="mt-1">
                    {agent.stats?.latest_certificate_grade ? (
                      <GradeBadge grade={agent.stats.latest_certificate_grade} size="lg" />
                    ) : (
                      <span className="text-3xl font-bold text-gray-300">--</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Recent Evaluations */}
              <div className="bg-white rounded-xl shadow-sm border border-gray-200">
                <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
                  <h2 className="text-lg font-semibold text-gray-900">Recent Evaluations</h2>
                  <button
                    onClick={() => setActiveTab("evaluations")}
                    className="text-sm text-primary-600 hover:underline"
                  >
                    View all
                  </button>
                </div>
                <div className="divide-y divide-gray-200">
                  {!evaluations?.items.length ? (
                    <div className="px-6 py-8 text-center">
                      <p className="text-gray-500 mb-4">No evaluations yet</p>
                      <button
                        onClick={() => setShowEvalModal(true)}
                        className="inline-flex items-center gap-2 text-primary-600 hover:underline"
                      >
                        <PlayIcon className="h-4 w-4" />
                        Run your first evaluation
                      </button>
                    </div>
                  ) : (
                    evaluations.items.slice(0, 3).map((evaluation) => (
                      <Link
                        key={evaluation.id}
                        href={`/evaluations/${evaluation.id}`}
                        className="px-6 py-4 flex items-center justify-between hover:bg-gray-50"
                      >
                        <div className="flex items-center gap-4">
                          {evaluation.grade && (
                            <GradeBadge grade={evaluation.grade} size="sm" />
                          )}
                          <div>
                            <p className="font-medium text-gray-900">
                              {evaluation.suites.join(", ")}
                            </p>
                            <p className="text-sm text-gray-500">
                              {formatDistanceToNow(new Date(evaluation.started_at), {
                                addSuffix: true,
                              })}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-4">
                          {evaluation.scores && (
                            <span className="font-medium text-gray-900">
                              {evaluation.scores.overall.toFixed(1)}%
                            </span>
                          )}
                          <StatusBadge status={evaluation.status} />
                        </div>
                      </Link>
                    ))
                  )}
                </div>
              </div>
            </div>

            {/* Sidebar */}
            <div className="space-y-6">
              {/* Agent Details */}
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                <h2 className="text-lg font-semibold text-gray-900 mb-4">Details</h2>
                <dl className="space-y-3">
                  <div className="flex justify-between">
                    <dt className="text-gray-500">Type</dt>
                    <dd className="font-medium text-gray-900">{agent.agent_type}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-500">Framework</dt>
                    <dd className="font-medium text-gray-900">{agent.framework || "custom"}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-500">Status</dt>
                    <dd><StatusBadge status={agent.status} /></dd>
                  </div>
                </dl>
                {agent.description && (
                  <div className="mt-4 pt-4 border-t border-gray-100">
                    <p className="text-sm text-gray-600">{agent.description}</p>
                  </div>
                )}
              </div>

              {/* Quick Setup Link */}
              <div className="bg-gradient-to-br from-primary-500 to-primary-700 rounded-xl p-6 text-white">
                <h3 className="font-semibold mb-2">Need help integrating?</h3>
                <p className="text-sm text-primary-100 mb-4">
                  Follow our step-by-step setup guide to start capturing traces.
                </p>
                <button
                  onClick={() => setActiveTab("setup")}
                  className="w-full bg-white text-primary-700 rounded-lg px-4 py-2 text-sm font-medium hover:bg-primary-50 transition-colors"
                >
                  View Setup Guide
                </button>
              </div>
            </div>
          </div>
        )}

        {activeTab === "setup" && (
          <div className="max-w-3xl">
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-2">{integration.title}</h2>
              <p className="text-gray-600">{integration.description}</p>
            </div>

            {/* Agent ID Card */}
            <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 mb-6">
              <p className="text-sm text-blue-700 mb-2 font-medium">Your Agent ID</p>
              <div className="flex items-center gap-2">
                <code className="flex-1 bg-white px-3 py-2 rounded-lg font-mono text-sm border border-blue-200">
                  {agent.id}
                </code>
                <CopyButton text={agent.id} />
              </div>
            </div>

            {/* Integration Steps */}
            <div className="space-y-6">
              {integration.steps.map((step, index) => (
                <div key={index} className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                  <h3 className="font-semibold text-gray-900 mb-4">{step.title}</h3>
                  <CodeBlock code={step.code} />
                </div>
              ))}
            </div>

            {/* Verification */}
            <div className="mt-6 bg-green-50 border border-green-200 rounded-xl p-6">
              <h3 className="font-semibold text-green-800 mb-2">Verify Integration</h3>
              <p className="text-sm text-green-700 mb-4">
                After setting up, make a test API call. You should see the trace appear in the Traces tab within a few seconds.
              </p>
              <button
                onClick={() => setActiveTab("traces")}
                className="inline-flex items-center gap-2 bg-green-600 text-white rounded-lg px-4 py-2 text-sm font-medium hover:bg-green-700 transition-colors"
              >
                <DocumentTextIcon className="h-4 w-4" />
                View Traces
              </button>
            </div>
          </div>
        )}

        {activeTab === "traces" && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">Traces</h2>
              <p className="text-sm text-gray-500 mt-1">
                Real-time view of all API calls made by this agent
              </p>
            </div>
            <div className="divide-y divide-gray-200">
              {!traces?.items?.length ? (
                <div className="px-6 py-12 text-center">
                  <DocumentTextIcon className="h-12 w-12 text-gray-300 mx-auto mb-4" />
                  <p className="text-gray-500 mb-2">No traces yet</p>
                  <p className="text-sm text-gray-400 mb-4">
                    Traces will appear here once your agent makes API calls
                  </p>
                  <button
                    onClick={() => setActiveTab("setup")}
                    className="text-primary-600 hover:underline text-sm"
                  >
                    View setup instructions
                  </button>
                </div>
              ) : (
                traces.items.map((trace: any) => (
                  <div key={trace.id} className="px-6 py-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium text-gray-900">{trace.name}</p>
                        <p className="text-sm text-gray-500">
                          {formatDistanceToNow(new Date(trace.started_at), { addSuffix: true })}
                        </p>
                      </div>
                      <div className="flex items-center gap-4">
                        <span className="text-sm text-gray-500">
                          {trace.metadata?.model || "unknown model"}
                        </span>
                        <span className={`px-2 py-1 rounded text-xs font-medium ${
                          trace.status === "ok"
                            ? "bg-green-100 text-green-700"
                            : "bg-red-100 text-red-700"
                        }`}>
                          {trace.status || "completed"}
                        </span>
                      </div>
                    </div>
                    {trace.metadata && (
                      <div className="mt-2 flex gap-4 text-xs text-gray-500">
                        {trace.metadata.input_tokens && (
                          <span>In: {trace.metadata.input_tokens} tokens</span>
                        )}
                        {trace.metadata.output_tokens && (
                          <span>Out: {trace.metadata.output_tokens} tokens</span>
                        )}
                        {trace.metadata.provider && (
                          <span>Provider: {trace.metadata.provider}</span>
                        )}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {activeTab === "evaluations" && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200">
            <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">Evaluations</h2>
                <p className="text-sm text-gray-500 mt-1">
                  All evaluation runs for this agent
                </p>
              </div>
              <button
                onClick={() => setShowEvalModal(true)}
                className="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
              >
                <PlayIcon className="h-4 w-4" />
                Run Evaluation
              </button>
            </div>
            <div className="divide-y divide-gray-200">
              {!evaluations?.items?.length ? (
                <div className="px-6 py-12 text-center">
                  <ShieldCheckIcon className="h-12 w-12 text-gray-300 mx-auto mb-4" />
                  <p className="text-gray-500 mb-2">No evaluations yet</p>
                  <p className="text-sm text-gray-400 mb-4">
                    Run an evaluation to test your agent&apos;s capabilities, safety, and reliability
                  </p>
                  <button
                    onClick={() => setShowEvalModal(true)}
                    className="inline-flex items-center gap-2 bg-primary-600 text-white rounded-lg px-4 py-2 text-sm font-medium hover:bg-primary-700"
                  >
                    <PlayIcon className="h-4 w-4" />
                    Run First Evaluation
                  </button>
                </div>
              ) : (
                evaluations.items.map((evaluation) => (
                  <Link
                    key={evaluation.id}
                    href={`/evaluations/${evaluation.id}`}
                    className="px-6 py-4 flex items-center justify-between hover:bg-gray-50"
                  >
                    <div className="flex items-center gap-4">
                      {evaluation.grade ? (
                        <GradeBadge grade={evaluation.grade} />
                      ) : (
                        <div className="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center">
                          <span className="text-gray-400 text-sm">--</span>
                        </div>
                      )}
                      <div>
                        <p className="font-medium text-gray-900">
                          {evaluation.suites.join(", ")}
                        </p>
                        <p className="text-sm text-gray-500">
                          {formatDistanceToNow(new Date(evaluation.started_at), {
                            addSuffix: true,
                          })}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      {evaluation.scores && (
                        <div className="text-right">
                          <p className="font-semibold text-gray-900">
                            {evaluation.scores.overall.toFixed(1)}%
                          </p>
                          <p className="text-xs text-gray-500">Overall Score</p>
                        </div>
                      )}
                      <StatusBadge status={evaluation.status} />
                    </div>
                  </Link>
                ))
              )}
            </div>
          </div>
        )}

        {/* Evaluation Modal */}
        {showEvalModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-white rounded-xl shadow-xl max-w-lg w-full mx-4 p-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-2">
                Run Evaluation
              </h2>
              <p className="text-gray-600 mb-6">
                Select the evaluation suites to test your agent&apos;s performance.
              </p>

              <div className="space-y-3 mb-6">
                {[
                  { id: "capability", name: "Capability", desc: "Tests task completion and tool usage" },
                  { id: "safety", name: "Safety", desc: "Tests for harmful outputs and prompt injection" },
                  { id: "reliability", name: "Reliability", desc: "Tests consistency and error handling" },
                  { id: "communication", name: "Communication", desc: "Tests clarity and appropriateness" },
                ].map((suite) => (
                  <label
                    key={suite.id}
                    className={`flex items-start gap-3 p-4 rounded-lg border cursor-pointer transition-colors ${
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
                      className="mt-0.5 rounded border-gray-300 text-primary-600 focus:ring-primary-500"
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
                  className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  onClick={() => startEvalMutation.mutate()}
                  disabled={startEvalMutation.isPending || selectedSuites.length === 0}
                  className="px-6 py-2 text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 rounded-lg disabled:opacity-50"
                >
                  {startEvalMutation.isPending ? "Starting..." : "Start Evaluation"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
