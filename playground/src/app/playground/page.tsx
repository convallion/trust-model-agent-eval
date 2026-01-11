"use client";

import { useState, useRef, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  PaperAirplaneIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  CpuChipIcon,
} from "@heroicons/react/24/outline";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { api } from "@/lib/api";

interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: Date;
  traceId?: string;
  latency?: number;
  status?: "success" | "error" | "pending";
  toolCalls?: { name: string; success: boolean; duration_ms?: number }[];
  model?: string;
  tokensUsed?: number;
}

export default function PlaygroundPage() {
  const [selectedAgent, setSelectedAgent] = useState<string>("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { data: agents } = useQuery({
    queryKey: ["agents"],
    queryFn: () => api.getAgents(),
  });

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const callRealAgent = async (userMessage: string) => {
    // Build conversation history for the API
    const conversationHistory = messages
      .filter((m) => m.role !== "system" && m.status !== "pending")
      .map((m) => ({
        role: m.role,
        content: m.content,
      }));

    // Add the new user message
    conversationHistory.push({
      role: "user",
      content: userMessage,
    });

    try {
      const response = await api.chat(selectedAgent, conversationHistory);

      return {
        content: response.content,
        latency: response.latency_ms,
        status: response.status,
        toolCalls: response.tool_calls || [],
        traceId: response.trace_id,
        model: response.model,
        tokensUsed: response.tokens_used,
      };
    } catch (error: any) {
      return {
        content: error.response?.data?.detail || error.message || "Failed to get response from agent",
        latency: 0,
        status: "error",
        toolCalls: [],
        traceId: `error-${Date.now()}`,
      };
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !selectedAgent) return;

    const userMessage: Message = {
      id: `msg-${Date.now()}`,
      role: "user",
      content: input,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    // Add pending assistant message
    const pendingId = `msg-${Date.now()}-pending`;
    setMessages((prev) => [
      ...prev,
      {
        id: pendingId,
        role: "assistant",
        content: "",
        timestamp: new Date(),
        status: "pending",
      },
    ]);

    try {
      const response = await callRealAgent(input);

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === pendingId
            ? {
                ...msg,
                content: response.content,
                latency: response.latency,
                status: response.status as "success" | "error",
                toolCalls: response.toolCalls,
                traceId: response.traceId,
                model: response.model,
                tokensUsed: response.tokensUsed,
              }
            : msg
        )
      );
    } catch (error) {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === pendingId
            ? {
                ...msg,
                content: "Failed to get response from agent",
                status: "error",
              }
            : msg
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  const getStatusIcon = (status?: string) => {
    switch (status) {
      case "success":
        return <CheckCircleIcon className="h-4 w-4 text-green-500" />;
      case "error":
        return <XCircleIcon className="h-4 w-4 text-red-500" />;
      case "pending":
        return <ClockIcon className="h-4 w-4 text-yellow-500 animate-pulse" />;
      default:
        return null;
    }
  };

  return (
    <DashboardLayout>
      <div className="h-[calc(100vh-8rem)] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Playground</h1>
            <p className="text-sm text-gray-500">
              Interact with your agent and observe its behavior
            </p>
          </div>
          <select
            value={selectedAgent}
            onChange={(e) => setSelectedAgent(e.target.value)}
            className="rounded-lg border border-gray-300 px-4 py-2 focus:ring-2 focus:ring-primary-500"
          >
            <option value="">Select an agent...</option>
            {agents?.items.map((agent) => (
              <option key={agent.id} value={agent.id}>
                {agent.name}
              </option>
            ))}
          </select>
        </div>

        {/* Main Content */}
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-4 min-h-0">
          {/* Chat Area */}
          <div className="lg:col-span-2 bg-white rounded-xl shadow-sm border border-gray-200 flex flex-col">
            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-gray-400">
                  <CpuChipIcon className="h-12 w-12 mb-2" />
                  <p>Select an agent and start chatting</p>
                </div>
              ) : (
                messages.map((message) => (
                  <div
                    key={message.id}
                    className={`flex ${
                      message.role === "user" ? "justify-end" : "justify-start"
                    }`}
                  >
                    <div
                      className={`max-w-[80%] rounded-xl px-4 py-3 ${
                        message.role === "user"
                          ? "bg-primary-600 text-white"
                          : "bg-gray-100 text-gray-900"
                      }`}
                    >
                      {message.status === "pending" ? (
                        <div className="flex items-center gap-2">
                          <div className="animate-pulse flex space-x-1">
                            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0.1s" }}></div>
                            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0.2s" }}></div>
                          </div>
                        </div>
                      ) : (
                        <>
                          <p className="whitespace-pre-wrap">{message.content}</p>
                          {message.role === "assistant" && (
                            <div className="mt-2 pt-2 border-t border-gray-200 flex items-center gap-3 text-xs text-gray-500">
                              {getStatusIcon(message.status)}
                              {message.latency && (
                                <span>{message.latency}ms</span>
                              )}
                              {message.traceId && (
                                <span className="font-mono">
                                  {message.traceId.slice(0, 12)}...
                                </span>
                              )}
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                ))
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <form
              onSubmit={handleSubmit}
              className="p-4 border-t border-gray-200"
            >
              <div className="flex gap-2">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  disabled={!selectedAgent || isLoading}
                  placeholder={
                    selectedAgent
                      ? "Type a message..."
                      : "Select an agent first"
                  }
                  className="flex-1 rounded-lg border border-gray-300 px-4 py-2 focus:ring-2 focus:ring-primary-500 disabled:bg-gray-50"
                />
                <button
                  type="submit"
                  disabled={!selectedAgent || !input.trim() || isLoading}
                  className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <PaperAirplaneIcon className="h-5 w-5" />
                </button>
              </div>
            </form>
          </div>

          {/* Observability Panel */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 overflow-y-auto">
            <h2 className="font-semibold text-gray-900 mb-4">Interaction Log</h2>

            {messages.filter((m) => m.role === "assistant" && m.status !== "pending").length === 0 ? (
              <p className="text-sm text-gray-500">
                Interactions will appear here
              </p>
            ) : (
              <div className="space-y-3">
                {messages
                  .filter((m) => m.role === "assistant" && m.status !== "pending")
                  .map((msg, idx) => (
                    <div
                      key={msg.id}
                      className={`p-3 rounded-lg border ${
                        msg.status === "success"
                          ? "border-green-200 bg-green-50"
                          : "border-red-200 bg-red-50"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-medium text-gray-500">
                          Interaction #{idx + 1}
                        </span>
                        {getStatusIcon(msg.status)}
                      </div>

                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <div>
                          <span className="text-gray-500">Latency:</span>
                          <span className={`ml-1 font-medium ${
                            (msg.latency || 0) < 1000 ? "text-green-600" : "text-yellow-600"
                          }`}>
                            {msg.latency}ms
                          </span>
                        </div>
                        <div>
                          <span className="text-gray-500">Status:</span>
                          <span className={`ml-1 font-medium ${
                            msg.status === "success" ? "text-green-600" : "text-red-600"
                          }`}>
                            {msg.status}
                          </span>
                        </div>
                      </div>

                      {msg.toolCalls && msg.toolCalls.length > 0 && (
                        <div className="mt-2 pt-2 border-t border-gray-200">
                          <span className="text-xs text-gray-500">Tool Calls:</span>
                          <div className="mt-1 flex flex-wrap gap-1">
                            {msg.toolCalls.map((tool, i) => (
                              <span
                                key={i}
                                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs ${
                                  tool.success
                                    ? "bg-green-100 text-green-700"
                                    : "bg-red-100 text-red-700"
                                }`}
                              >
                                {tool.success ? (
                                  <CheckCircleIcon className="h-3 w-3" />
                                ) : (
                                  <XCircleIcon className="h-3 w-3" />
                                )}
                                {tool.name}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {msg.traceId && (
                        <div className="mt-2 pt-2 border-t border-gray-200">
                          <span className="text-xs text-gray-500">Trace ID:</span>
                          <code className="ml-1 text-xs font-mono text-gray-700">
                            {msg.traceId}
                          </code>
                        </div>
                      )}
                    </div>
                  ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
