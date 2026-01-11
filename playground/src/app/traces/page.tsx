"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { api, type Trace } from "@/lib/api";
import { StatusBadge } from "@/components/ui/StatusBadge";

export default function TracesPage() {
  const [selectedTrace, setSelectedTrace] = useState<string | null>(null);

  const { data: traces, isLoading } = useQuery({
    queryKey: ["traces"],
    queryFn: () => api.getTraces(),
  });

  const { data: traceDetail } = useQuery({
    queryKey: ["trace", selectedTrace],
    queryFn: () => api.getTrace(selectedTrace!),
    enabled: !!selectedTrace,
  });

  return (
    <DashboardLayout>
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Traces</h1>
        <p className="mt-1 text-sm text-gray-500">
          View execution traces from your agents
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Trace List */}
        <div className="lg:col-span-1 bg-white rounded-xl shadow-sm border border-gray-200">
          <div className="px-4 py-3 border-b border-gray-200">
            <h2 className="font-medium text-gray-900">Recent Traces</h2>
          </div>
          <div className="divide-y divide-gray-200 max-h-[600px] overflow-auto">
            {isLoading ? (
              <div className="p-4 text-center text-gray-500">Loading...</div>
            ) : traces?.items.length === 0 ? (
              <div className="p-4 text-center text-gray-500">
                No traces yet
              </div>
            ) : (
              traces?.items.map((trace) => (
                <button
                  key={trace.id}
                  onClick={() => setSelectedTrace(trace.id)}
                  className={`w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors ${
                    selectedTrace === trace.id ? "bg-primary-50" : ""
                  }`}
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="text-sm font-medium text-gray-900">
                        {trace.id.slice(0, 8)}...
                      </p>
                      <p className="text-xs text-gray-500">
                        {trace.spans?.length || 0} spans
                      </p>
                    </div>
                    <span className="text-xs text-gray-400">
                      {formatDistanceToNow(new Date(trace.started_at), {
                        addSuffix: true,
                      })}
                    </span>
                  </div>
                </button>
              ))
            )}
          </div>
        </div>

        {/* Trace Detail / Timeline */}
        <div className="lg:col-span-2 bg-white rounded-xl shadow-sm border border-gray-200">
          <div className="px-4 py-3 border-b border-gray-200">
            <h2 className="font-medium text-gray-900">Trace Timeline</h2>
          </div>
          {selectedTrace && traceDetail ? (
            <div className="p-4">
              <div className="mb-4">
                <dl className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <dt className="text-gray-500">Trace ID</dt>
                    <dd className="font-mono text-gray-900">{traceDetail.id}</dd>
                  </div>
                  <div>
                    <dt className="text-gray-500">Duration</dt>
                    <dd className="text-gray-900">
                      {traceDetail.ended_at
                        ? `${(
                            (new Date(traceDetail.ended_at).getTime() -
                              new Date(traceDetail.started_at).getTime()) /
                            1000
                          ).toFixed(2)}s`
                        : "In progress"}
                    </dd>
                  </div>
                </dl>
              </div>

              {/* Span Timeline */}
              <div className="trace-timeline space-y-4 pl-10">
                {traceDetail.spans?.map((span, index) => (
                  <div key={span.id} className="relative">
                    <div
                      className={`absolute -left-10 top-1 w-4 h-4 rounded-full border-2 border-white shadow ${
                        span.span_type === "llm_call"
                          ? "bg-purple-500"
                          : span.span_type === "tool_call"
                          ? "bg-blue-500"
                          : "bg-gray-400"
                      }`}
                    />
                    <div className="bg-gray-50 rounded-lg p-4">
                      <div className="flex justify-between items-start">
                        <div>
                          <p className="font-medium text-gray-900">
                            {span.name}
                          </p>
                          <p className="text-sm text-gray-500 mt-1">
                            {span.span_type}
                          </p>
                        </div>
                        <StatusBadge status={span.status} />
                      </div>
                      {span.attributes && Object.keys(span.attributes).length > 0 && (
                        <div className="mt-3 text-sm">
                          <details>
                            <summary className="cursor-pointer text-gray-500 hover:text-gray-700">
                              Attributes
                            </summary>
                            <pre className="mt-2 p-2 bg-gray-100 rounded text-xs overflow-auto max-h-32">
                              {JSON.stringify(span.attributes, null, 2)}
                            </pre>
                          </details>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="p-8 text-center text-gray-500">
              Select a trace to view details
            </div>
          )}
        </div>
      </div>
    </div>
    </DashboardLayout>
  );
}
