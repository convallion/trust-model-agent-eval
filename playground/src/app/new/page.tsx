"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import {
  ArrowLeftIcon,
  CheckCircleIcon,
  ShieldCheckIcon,
  BoltIcon,
  SparklesIcon,
  ExclamationCircleIcon,
  ArrowPathIcon,
  CpuChipIcon,
  BeakerIcon,
  LockClosedIcon,
  ClockIcon,
} from "@heroicons/react/24/outline";
import { CheckCircleIcon as CheckCircleSolid } from "@heroicons/react/24/solid";
import { api } from "@/lib/api";

type AgentSource = "langsmith" | "openai" | "anthropic" | "custom";
type Step = "source" | "details" | "testing" | "connected" | "evaluations" | "name" | "creating";

const SOURCES = [
  {
    id: "langsmith" as AgentSource,
    name: "LangSmith / LangGraph",
    description: "Connect a deployed LangGraph agent",
    icon: "🦜",
  },
  {
    id: "anthropic" as AgentSource,
    name: "Anthropic API",
    description: "Direct Claude API integration",
    icon: "🤖",
  },
  {
    id: "openai" as AgentSource,
    name: "OpenAI API",
    description: "GPT-based agent",
    icon: "⚡",
  },
  {
    id: "custom" as AgentSource,
    name: "Custom HTTP",
    description: "Any REST API endpoint",
    icon: "🔧",
  },
];

const EVAL_SUITES = [
  {
    id: "capability",
    name: "Capability",
    description: "Task completion, reasoning, tool use",
    icon: BeakerIcon,
    recommended: true,
  },
  {
    id: "safety",
    name: "Safety",
    description: "Jailbreak resistance, harmful content",
    icon: ShieldCheckIcon,
    recommended: true,
  },
  {
    id: "reliability",
    name: "Reliability",
    description: "Consistency, error handling",
    icon: ClockIcon,
    recommended: false,
  },
];

export default function NewAgentPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("source");
  const [source, setSource] = useState<AgentSource | null>(null);
  const [agentUrl, setAgentUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [agentName, setAgentName] = useState("");
  const [selectedEvals, setSelectedEvals] = useState<string[]>(["capability", "safety"]);
  const [error, setError] = useState("");

  // Test connection
  const testMutation = useMutation({
    mutationFn: async () => {
      const response = await fetch("/api/test-agent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: agentUrl, apiKey }),
      });
      const data = await response.json();
      if (!response.ok || !data.success) {
        throw new Error(data.message || "Connection failed");
      }
      return data;
    },
    onSuccess: () => {
      setStep("connected");
      setError("");
    },
    onError: (err: any) => {
      setError(err.message);
      setStep("details");
    },
  });

  // Create agent
  const createMutation = useMutation({
    mutationFn: async () => {
      const agent = await api.createAgent({
        name: agentName,
        agent_type: "custom",
        framework: source || "custom",
        description: `${source} agent`,
        metadata: {
          executor_type: source === "langsmith" ? "langsmith" : "http",
          langsmith_api_url: agentUrl,
          api_key: apiKey || undefined,
        },
      });
      await api.startEvaluation(agent.id, selectedEvals);
      return agent;
    },
    onSuccess: (agent) => {
      router.push(`/agents/${agent.id}`);
    },
    onError: (err: any) => {
      setError(err.response?.data?.detail || "Failed to create agent");
      setStep("name");
    },
  });

  const handleTestConnection = () => {
    if (!agentUrl) {
      setError("Please enter the agent URL");
      return;
    }
    setError("");
    setStep("testing");
    testMutation.mutate();
  };

  const handleCreate = () => {
    if (!agentName.trim()) {
      setError("Please enter a name for your agent");
      return;
    }
    setError("");
    setStep("creating");
    createMutation.mutate();
  };

  const toggleEval = (id: string) => {
    setSelectedEvals((prev) =>
      prev.includes(id) ? prev.filter((e) => e !== id) : [...prev, id]
    );
  };

  // Progress indicator
  const steps = ["source", "details", "testing", "connected", "evaluations", "name", "creating"];
  const currentIndex = steps.indexOf(step);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      {/* Background effects */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-96 h-96 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-pulse" />
        <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-blue-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-pulse" />
      </div>

      <div className="relative z-10 min-h-screen">
        {/* Header */}
        <header className="p-6">
          <Link href="/" className="inline-flex items-center gap-2 text-white/60 hover:text-white transition-colors">
            <ArrowLeftIcon className="w-4 h-4" />
            Back
          </Link>
        </header>

        {/* Main */}
        <main className="flex items-center justify-center px-6 pb-12">
          <div className="w-full max-w-xl">
            {/* Progress bar */}
            <div className="mb-8">
              <div className="h-1 bg-white/10 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-green-400 to-emerald-500 transition-all duration-500"
                  style={{ width: `${((currentIndex + 1) / steps.length) * 100}%` }}
                />
              </div>
            </div>

            {/* Card */}
            <div className="bg-white/10 backdrop-blur-xl rounded-3xl border border-white/20 overflow-hidden shadow-2xl">
              {/* ==================== STEP: SOURCE ==================== */}
              {step === "source" && (
                <div className="p-8">
                  <div className="text-center mb-8">
                    <div className="w-16 h-16 bg-white/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
                      <CpuChipIcon className="w-8 h-8 text-white" />
                    </div>
                    <h1 className="text-2xl font-bold text-white">Select Agent Source</h1>
                    <p className="text-white/60 mt-2">Where is your agent deployed?</p>
                  </div>

                  <div className="space-y-3">
                    {SOURCES.map((s) => (
                      <button
                        key={s.id}
                        onClick={() => {
                          setSource(s.id);
                          setStep("details");
                        }}
                        className="w-full p-4 bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 rounded-2xl text-left transition-all group"
                      >
                        <div className="flex items-center gap-4">
                          <span className="text-3xl">{s.icon}</span>
                          <div className="flex-1">
                            <p className="font-semibold text-white group-hover:text-white">{s.name}</p>
                            <p className="text-sm text-white/50">{s.description}</p>
                          </div>
                          <ArrowPathIcon className="w-5 h-5 text-white/30 group-hover:text-white/60 group-hover:translate-x-1 transition-all" />
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* ==================== STEP: DETAILS ==================== */}
              {step === "details" && (
                <div className="p-8">
                  <div className="text-center mb-8">
                    <div className="w-16 h-16 bg-white/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
                      <span className="text-3xl">{SOURCES.find((s) => s.id === source)?.icon}</span>
                    </div>
                    <h1 className="text-2xl font-bold text-white">Connection Details</h1>
                    <p className="text-white/60 mt-2">Enter your {SOURCES.find((s) => s.id === source)?.name} details</p>
                  </div>

                  {error && (
                    <div className="mb-6 p-4 bg-red-500/20 border border-red-500/30 rounded-xl flex items-start gap-3">
                      <ExclamationCircleIcon className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
                      <p className="text-red-200 text-sm">{error}</p>
                    </div>
                  )}

                  <div className="space-y-4">
                    <div>
                      <label className="block text-white/60 text-sm mb-2">
                        {source === "langsmith" ? "LangGraph URL" : "API Endpoint URL"}
                      </label>
                      <input
                        type="url"
                        value={agentUrl}
                        onChange={(e) => setAgentUrl(e.target.value)}
                        placeholder={
                          source === "langsmith"
                            ? "https://your-agent.us.langgraph.app"
                            : "https://api.example.com/v1/chat"
                        }
                        className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-xl text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-white/30"
                        autoFocus
                      />
                    </div>

                    <div>
                      <label className="block text-white/60 text-sm mb-2">
                        API Key {source !== "langsmith" && "(optional)"}
                      </label>
                      <input
                        type="password"
                        value={apiKey}
                        onChange={(e) => setApiKey(e.target.value)}
                        placeholder="sk-..."
                        className="w-full px-4 py-3 bg-white/10 border border-white/20 rounded-xl text-white placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-white/30"
                      />
                    </div>
                  </div>

                  <div className="flex gap-3 mt-8">
                    <button
                      onClick={() => setStep("source")}
                      className="px-6 py-3 bg-white/10 text-white rounded-xl font-medium hover:bg-white/20 transition-colors"
                    >
                      Back
                    </button>
                    <button
                      onClick={handleTestConnection}
                      className="flex-1 py-3 bg-white text-slate-900 rounded-xl font-semibold hover:bg-white/90 transition-colors flex items-center justify-center gap-2"
                    >
                      <BoltIcon className="w-5 h-5" />
                      Test Connection
                    </button>
                  </div>
                </div>
              )}

              {/* ==================== STEP: TESTING ==================== */}
              {step === "testing" && (
                <div className="p-8 py-16">
                  <div className="text-center">
                    <div className="w-20 h-20 mx-auto mb-6 relative">
                      <div className="absolute inset-0 rounded-full border-4 border-white/20" />
                      <div className="absolute inset-0 rounded-full border-4 border-white border-t-transparent animate-spin" />
                    </div>
                    <h2 className="text-xl font-semibold text-white mb-2">Testing Connection</h2>
                    <p className="text-white/50 text-sm truncate max-w-xs mx-auto">{agentUrl}</p>
                  </div>
                </div>
              )}

              {/* ==================== STEP: CONNECTED ==================== */}
              {step === "connected" && (
                <div className="p-8">
                  <div className="text-center mb-8">
                    <div className="w-16 h-16 bg-green-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
                      <CheckCircleSolid className="w-10 h-10 text-green-400" />
                    </div>
                    <h1 className="text-2xl font-bold text-white">Connected!</h1>
                    <p className="text-green-400 mt-2">Your agent is online and responding</p>
                  </div>

                  <button
                    onClick={() => setStep("evaluations")}
                    className="w-full py-4 bg-gradient-to-r from-green-400 to-emerald-500 text-slate-900 rounded-xl font-semibold text-lg hover:opacity-90 transition-all"
                  >
                    Continue to Evaluation Setup
                  </button>
                </div>
              )}

              {/* ==================== STEP: EVALUATIONS ==================== */}
              {step === "evaluations" && (
                <div className="p-8">
                  <div className="text-center mb-8">
                    <div className="w-16 h-16 bg-white/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
                      <BeakerIcon className="w-8 h-8 text-white" />
                    </div>
                    <h1 className="text-2xl font-bold text-white">Choose Evaluations</h1>
                    <p className="text-white/60 mt-2">Select what to test</p>
                  </div>

                  <div className="space-y-3 mb-8">
                    {EVAL_SUITES.map((suite) => {
                      const isSelected = selectedEvals.includes(suite.id);
                      const Icon = suite.icon;

                      return (
                        <button
                          key={suite.id}
                          onClick={() => toggleEval(suite.id)}
                          className={`w-full p-4 rounded-2xl border text-left transition-all ${
                            isSelected
                              ? "bg-white/15 border-green-500/50"
                              : "bg-white/5 border-white/10 hover:bg-white/10"
                          }`}
                        >
                          <div className="flex items-center gap-4">
                            <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                              isSelected ? "bg-green-500/20" : "bg-white/10"
                            }`}>
                              <Icon className={`w-5 h-5 ${isSelected ? "text-green-400" : "text-white/60"}`} />
                            </div>
                            <div className="flex-1">
                              <div className="flex items-center gap-2">
                                <p className="font-semibold text-white">{suite.name}</p>
                                {suite.recommended && (
                                  <span className="text-xs bg-green-500/20 text-green-400 px-2 py-0.5 rounded-full">
                                    Recommended
                                  </span>
                                )}
                              </div>
                              <p className="text-sm text-white/50">{suite.description}</p>
                            </div>
                            <div className={`w-6 h-6 rounded-full border-2 flex items-center justify-center ${
                              isSelected ? "border-green-400 bg-green-400" : "border-white/30"
                            }`}>
                              {isSelected && <CheckCircleSolid className="w-4 h-4 text-slate-900" />}
                            </div>
                          </div>
                        </button>
                      );
                    })}
                  </div>

                  <div className="flex gap-3">
                    <button
                      onClick={() => setStep("connected")}
                      className="px-6 py-3 bg-white/10 text-white rounded-xl font-medium hover:bg-white/20 transition-colors"
                    >
                      Back
                    </button>
                    <button
                      onClick={() => setStep("name")}
                      disabled={selectedEvals.length === 0}
                      className="flex-1 py-3 bg-white text-slate-900 rounded-xl font-semibold hover:bg-white/90 disabled:opacity-50 transition-colors"
                    >
                      Continue
                    </button>
                  </div>
                </div>
              )}

              {/* ==================== STEP: NAME ==================== */}
              {step === "name" && (
                <div className="p-8">
                  <div className="text-center mb-8">
                    <div className="w-16 h-16 bg-white/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
                      <SparklesIcon className="w-8 h-8 text-white" />
                    </div>
                    <h1 className="text-2xl font-bold text-white">Name Your Agent</h1>
                    <p className="text-white/60 mt-2">Give it a memorable name</p>
                  </div>

                  {error && (
                    <div className="mb-6 p-4 bg-red-500/20 border border-red-500/30 rounded-xl text-red-200 text-sm">
                      {error}
                    </div>
                  )}

                  <input
                    type="text"
                    value={agentName}
                    onChange={(e) => setAgentName(e.target.value)}
                    placeholder="My Calendar Agent"
                    className="w-full px-4 py-4 bg-white/10 border border-white/20 rounded-xl text-white text-lg placeholder-white/40 focus:outline-none focus:ring-2 focus:ring-white/30 mb-6"
                    autoFocus
                  />

                  {/* Summary */}
                  <div className="bg-white/5 rounded-xl p-4 mb-6 space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-white/50">Source</span>
                      <span className="text-white">{SOURCES.find((s) => s.id === source)?.name}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-white/50">Evaluations</span>
                      <span className="text-white">{selectedEvals.join(", ")}</span>
                    </div>
                  </div>

                  <div className="flex gap-3">
                    <button
                      onClick={() => setStep("evaluations")}
                      className="px-6 py-3 bg-white/10 text-white rounded-xl font-medium hover:bg-white/20 transition-colors"
                    >
                      Back
                    </button>
                    <button
                      onClick={handleCreate}
                      className="flex-1 py-4 bg-gradient-to-r from-green-400 to-emerald-500 text-slate-900 rounded-xl font-semibold text-lg hover:opacity-90 transition-all flex items-center justify-center gap-2"
                    >
                      <SparklesIcon className="w-5 h-5" />
                      Create & Start Evaluation
                    </button>
                  </div>
                </div>
              )}

              {/* ==================== STEP: CREATING ==================== */}
              {step === "creating" && (
                <div className="p-8 py-16">
                  <div className="text-center">
                    <div className="w-20 h-20 mx-auto mb-6 relative">
                      <div className="absolute inset-0 rounded-full border-4 border-green-500/20" />
                      <div className="absolute inset-0 rounded-full border-4 border-green-400 border-t-transparent animate-spin" />
                    </div>
                    <h2 className="text-xl font-semibold text-white mb-2">Creating Agent</h2>
                    <p className="text-white/50">Starting evaluation...</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
