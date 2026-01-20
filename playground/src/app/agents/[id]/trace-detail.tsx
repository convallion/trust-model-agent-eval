"use client";

import { useState } from "react";
import { formatDistanceToNow } from "date-fns";
import {
  ChevronDownIcon,
  ChevronRightIcon,
  UserIcon,
  CpuChipIcon,
  WrenchScrewdriverIcon,
  ClockIcon,
  DocumentTextIcon,
} from "@heroicons/react/24/outline";

interface Message {
  type: string;
  content: string;
  name?: string;
  tool_calls?: ToolCall[];
  tool_call_id?: string;
  usage_metadata?: {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
  };
  response_metadata?: {
    model_name?: string;
    finish_reason?: string;
  };
}

interface ToolCall {
  name: string;
  args: Record<string, any>;
  id: string;
}

interface TraceDetailProps {
  trace: {
    id: string;
    created_at: string;
    updated_at: string;
    status: string;
    messages: Message[];
    metadata?: Record<string, any>;
  };
  onClose: () => void;
}

function MessageIcon({ type }: { type: string }) {
  switch (type) {
    case "human":
      return <UserIcon className="w-5 h-5 text-blue-600" />;
    case "ai":
      return <CpuChipIcon className="w-5 h-5 text-purple-600" />;
    case "tool":
      return <WrenchScrewdriverIcon className="w-5 h-5 text-green-600" />;
    default:
      return <DocumentTextIcon className="w-5 h-5 text-gray-600" />;
  }
}

function ToolCallCard({ toolCall, toolResponse }: { toolCall: ToolCall; toolResponse?: Message }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border border-green-200 rounded-lg overflow-hidden bg-green-50">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 flex items-center gap-3 hover:bg-green-100 transition-colors"
      >
        {expanded ? (
          <ChevronDownIcon className="w-4 h-4 text-green-600" />
        ) : (
          <ChevronRightIcon className="w-4 h-4 text-green-600" />
        )}
        <WrenchScrewdriverIcon className="w-5 h-5 text-green-600" />
        <span className="font-medium text-green-800">{toolCall.name}</span>
        {toolResponse && (
          <span className="ml-auto text-xs text-green-600 bg-green-200 px-2 py-0.5 rounded">
            completed
          </span>
        )}
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-3">
          <div>
            <p className="text-xs font-medium text-green-700 mb-1">Input Arguments:</p>
            <pre className="text-xs bg-white p-3 rounded border border-green-200 overflow-x-auto">
              {JSON.stringify(toolCall.args, null, 2)}
            </pre>
          </div>

          {toolResponse && (
            <div>
              <p className="text-xs font-medium text-green-700 mb-1">Output:</p>
              <pre className="text-xs bg-white p-3 rounded border border-green-200 overflow-x-auto max-h-60 overflow-y-auto">
                {typeof toolResponse.content === "string"
                  ? tryFormatJSON(toolResponse.content)
                  : JSON.stringify(toolResponse.content, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function tryFormatJSON(str: string): string {
  try {
    const parsed = JSON.parse(str);
    return JSON.stringify(parsed, null, 2);
  } catch {
    return str;
  }
}

function AIMessageCard({ message, toolResponses }: { message: Message; toolResponses: Map<string, Message> }) {
  const [expanded, setExpanded] = useState(true);
  const hasToolCalls = message.tool_calls && message.tool_calls.length > 0;
  const hasContent = message.content && message.content.trim().length > 0;

  return (
    <div className="border border-purple-200 rounded-lg overflow-hidden">
      <div className="px-4 py-3 bg-purple-50 flex items-center gap-3">
        <CpuChipIcon className="w-5 h-5 text-purple-600" />
        <span className="font-medium text-purple-800">AI Response</span>
        {message.response_metadata?.model_name && (
          <span className="text-xs text-purple-600 bg-purple-200 px-2 py-0.5 rounded">
            {message.response_metadata.model_name}
          </span>
        )}
        {message.usage_metadata && (
          <span className="ml-auto text-xs text-purple-600">
            {message.usage_metadata.total_tokens.toLocaleString()} tokens
          </span>
        )}
      </div>

      <div className="p-4 space-y-4">
        {/* Tool Calls */}
        {hasToolCalls && (
          <div className="space-y-2">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Tool Calls</p>
            {message.tool_calls!.map((tc) => (
              <ToolCallCard
                key={tc.id}
                toolCall={tc}
                toolResponse={toolResponses.get(tc.id)}
              />
            ))}
          </div>
        )}

        {/* Text Response */}
        {hasContent && (
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Response</p>
            <div className="prose prose-sm max-w-none text-gray-800 whitespace-pre-wrap">
              {message.content}
            </div>
          </div>
        )}

        {/* Token Usage Details */}
        {message.usage_metadata && (
          <div className="pt-3 border-t border-gray-200">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Usage</p>
            <div className="flex gap-4 text-xs text-gray-600">
              <span>Input: {message.usage_metadata.input_tokens.toLocaleString()}</span>
              <span>Output: {message.usage_metadata.output_tokens.toLocaleString()}</span>
              <span>Total: {message.usage_metadata.total_tokens.toLocaleString()}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export function TraceDetail({ trace, onClose }: TraceDetailProps) {
  // Build a map of tool responses by tool_call_id
  const toolResponses = new Map<string, Message>();
  trace.messages.forEach((msg) => {
    if (msg.type === "tool" && msg.tool_call_id) {
      toolResponses.set(msg.tool_call_id, msg);
    }
  });

  // Filter to show human and AI messages (tool responses are shown inline)
  const displayMessages = trace.messages.filter((msg) => msg.type !== "tool");

  // Calculate totals
  const totalTokens = trace.messages
    .filter((m) => m.usage_metadata)
    .reduce((sum, m) => sum + (m.usage_metadata?.total_tokens || 0), 0);

  const toolCallCount = trace.messages
    .filter((m) => m.tool_calls)
    .reduce((sum, m) => sum + (m.tool_calls?.length || 0), 0);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-xl max-w-4xl w-full max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Trace Details</h2>
            <p className="text-sm text-gray-500">
              Thread: {trace.id.slice(0, 8)}... •{" "}
              {formatDistanceToNow(new Date(trace.created_at), { addSuffix: true })}
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-xl font-bold"
          >
            ×
          </button>
        </div>

        {/* Stats */}
        <div className="px-6 py-3 bg-gray-50 border-b border-gray-200 flex gap-6">
          <div className="flex items-center gap-2 text-sm">
            <DocumentTextIcon className="w-4 h-4 text-gray-500" />
            <span className="text-gray-600">{trace.messages.length} messages</span>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <WrenchScrewdriverIcon className="w-4 h-4 text-gray-500" />
            <span className="text-gray-600">{toolCallCount} tool calls</span>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <CpuChipIcon className="w-4 h-4 text-gray-500" />
            <span className="text-gray-600">{totalTokens.toLocaleString()} total tokens</span>
          </div>
          <div className="flex items-center gap-2 text-sm ml-auto">
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${
              trace.status === "idle" ? "bg-green-100 text-green-700" :
              trace.status === "busy" ? "bg-blue-100 text-blue-700" :
              "bg-gray-100 text-gray-700"
            }`}>
              {trace.status}
            </span>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {displayMessages.map((message, idx) => {
            if (message.type === "human") {
              return (
                <div key={idx} className="border border-blue-200 rounded-lg overflow-hidden">
                  <div className="px-4 py-3 bg-blue-50 flex items-center gap-3">
                    <UserIcon className="w-5 h-5 text-blue-600" />
                    <span className="font-medium text-blue-800">User</span>
                  </div>
                  <div className="p-4">
                    <p className="text-gray-800">{message.content}</p>
                  </div>
                </div>
              );
            }

            if (message.type === "ai") {
              return (
                <AIMessageCard
                  key={idx}
                  message={message}
                  toolResponses={toolResponses}
                />
              );
            }

            return null;
          })}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg font-medium hover:bg-gray-200 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
