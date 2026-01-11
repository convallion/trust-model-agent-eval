"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  ExclamationTriangleIcon,
  CpuChipIcon,
} from "@heroicons/react/24/outline";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { api, ObservabilityMetrics } from "@/lib/api";

export default function ObservabilityPage() {
  const [timeRange, setTimeRange] = useState("24");
  const [selectedAgent, setSelectedAgent] = useState<string>("");

  const { data: agents } = useQuery({
    queryKey: ["agents"],
    queryFn: () => api.getAgents(),
  });

  const { data: metrics, isLoading, error } = useQuery({
    queryKey: ["observability-metrics", timeRange, selectedAgent],
    queryFn: () => api.getObservabilityMetrics(
      parseInt(timeRange),
      selectedAgent || undefined
    ),
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  const StatCard = ({
    title,
    value,
    subtitle,
    icon: Icon,
    color,
  }: {
    title: string;
    value: string | number;
    subtitle?: string;
    icon: any;
    color: string;
  }) => (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500">{title}</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
          {subtitle && (
            <p className="text-sm text-gray-500 mt-1">{subtitle}</p>
          )}
        </div>
        <div className={`p-3 rounded-lg ${color}`}>
          <Icon className="h-6 w-6 text-white" />
        </div>
      </div>
    </div>
  );

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
        </div>
      </DashboardLayout>
    );
  }

  // Use metrics or show empty state
  const hasData = metrics && metrics.total_requests > 0;

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Observability</h1>
            <p className="text-sm text-gray-500">
              Monitor agent performance, errors, and interactions
            </p>
          </div>
          <div className="flex items-center gap-3">
            <select
              value={selectedAgent}
              onChange={(e) => setSelectedAgent(e.target.value)}
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500"
            >
              <option value="">All Agents</option>
              {agents?.items.map((agent) => (
                <option key={agent.id} value={agent.id}>
                  {agent.name}
                </option>
              ))}
            </select>
            <select
              value={timeRange}
              onChange={(e) => setTimeRange(e.target.value)}
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500"
            >
              <option value="1">Last 1 hour</option>
              <option value="6">Last 6 hours</option>
              <option value="24">Last 24 hours</option>
              <option value="168">Last 7 days</option>
            </select>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <StatCard
            title="Total Requests"
            value={metrics?.total_requests?.toLocaleString() || "0"}
            subtitle={`${metrics?.success_count || 0} successful`}
            icon={CheckCircleIcon}
            color="bg-blue-500"
          />
          <StatCard
            title="Success Rate"
            value={`${(metrics?.success_rate || 100).toFixed(1)}%`}
            subtitle="Based on span status"
            icon={CheckCircleIcon}
            color="bg-green-500"
          />
          <StatCard
            title="Avg Latency"
            value={`${Math.round(metrics?.avg_latency_ms || 0)}ms`}
            subtitle="Per span"
            icon={ClockIcon}
            color="bg-purple-500"
          />
          <StatCard
            title="Total Errors"
            value={metrics?.error_count || 0}
            subtitle={metrics?.error_count === 0 ? "No errors!" : "Needs review"}
            icon={XCircleIcon}
            color="bg-red-500"
          />
        </div>

        {!hasData ? (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center">
            <CpuChipIcon className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-gray-900 mb-2">No data yet</h3>
            <p className="text-gray-500 max-w-md mx-auto">
              Start interacting with your agents in the Playground to see real-time metrics here.
              Traces and spans will appear as your agents process requests.
            </p>
          </div>
        ) : (
          <>
            {/* Charts Row */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Request Chart */}
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                <h2 className="font-semibold text-gray-900 mb-4">Requests Over Time</h2>
                <div className="h-64 flex items-end gap-1">
                  {metrics?.requests_over_time && metrics.requests_over_time.length > 0 ? (
                    metrics.requests_over_time.map((point, idx) => {
                      const maxValue = Math.max(...metrics.requests_over_time.map(p => p.value), 1);
                      return (
                        <div
                          key={idx}
                          className="flex-1 bg-primary-500 rounded-t hover:bg-primary-600 transition-colors cursor-pointer group relative"
                          style={{ height: `${Math.max((point.value / maxValue) * 100, 2)}%` }}
                          title={`${point.timestamp}: ${point.value} requests`}
                        >
                          <div className="hidden group-hover:block absolute -top-8 left-1/2 -translate-x-1/2 bg-gray-800 text-white text-xs px-2 py-1 rounded whitespace-nowrap z-10">
                            {point.value} req
                          </div>
                        </div>
                      );
                    })
                  ) : (
                    <div className="flex-1 flex items-center justify-center text-gray-400">
                      No request data
                    </div>
                  )}
                </div>
                {metrics?.requests_over_time && metrics.requests_over_time.length > 0 && (
                  <div className="flex justify-between mt-2 text-xs text-gray-500">
                    <span>{metrics.requests_over_time[0]?.timestamp}</span>
                    <span>{metrics.requests_over_time[metrics.requests_over_time.length - 1]?.timestamp}</span>
                  </div>
                )}
              </div>

              {/* Error Chart */}
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                <h2 className="font-semibold text-gray-900 mb-4">Errors Over Time</h2>
                <div className="h-64 flex items-end gap-1">
                  {metrics?.errors_over_time && metrics.errors_over_time.length > 0 ? (
                    metrics.errors_over_time.map((point, idx) => {
                      const maxValue = Math.max(...metrics.errors_over_time.map(p => p.value), 1);
                      return (
                        <div
                          key={idx}
                          className="flex-1 bg-red-500 rounded-t hover:bg-red-600 transition-colors cursor-pointer group relative"
                          style={{ height: `${Math.max((point.value / maxValue) * 100, point.value > 0 ? 5 : 2)}%` }}
                          title={`${point.timestamp}: ${point.value} errors`}
                        >
                          <div className="hidden group-hover:block absolute -top-8 left-1/2 -translate-x-1/2 bg-gray-800 text-white text-xs px-2 py-1 rounded whitespace-nowrap z-10">
                            {point.value} err
                          </div>
                        </div>
                      );
                    })
                  ) : (
                    <div className="flex-1 flex items-center justify-center text-gray-400">
                      No error data
                    </div>
                  )}
                </div>
                {metrics?.errors_over_time && metrics.errors_over_time.length > 0 && (
                  <div className="flex justify-between mt-2 text-xs text-gray-500">
                    <span>{metrics.errors_over_time[0]?.timestamp}</span>
                    <span>{metrics.errors_over_time[metrics.errors_over_time.length - 1]?.timestamp}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Bottom Row */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Recent Errors */}
              <div className="bg-white rounded-xl shadow-sm border border-gray-200">
                <div className="px-6 py-4 border-b border-gray-200">
                  <h2 className="font-semibold text-gray-900">Recent Errors</h2>
                </div>
                {metrics?.recent_errors && metrics.recent_errors.length > 0 ? (
                  <div className="divide-y divide-gray-200">
                    {metrics.recent_errors.map((error) => (
                      <div key={error.id} className="px-6 py-4 flex items-center gap-4">
                        <div className="p-2 bg-red-100 rounded-lg">
                          <ExclamationTriangleIcon className="h-5 w-5 text-red-600" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-gray-900 truncate">{error.message}</p>
                          <p className="text-sm text-gray-500">
                            {error.agent_name} - {error.timestamp ? new Date(error.timestamp).toLocaleString() : "Unknown time"}
                          </p>
                        </div>
                        <a
                          href={`/traces/${error.trace_id}`}
                          className="text-sm text-primary-600 hover:text-primary-700"
                        >
                          View Trace
                        </a>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="px-6 py-8 text-center text-gray-500">
                    No recent errors
                  </div>
                )}
              </div>

              {/* Top Agents */}
              <div className="bg-white rounded-xl shadow-sm border border-gray-200">
                <div className="px-6 py-4 border-b border-gray-200">
                  <h2 className="font-semibold text-gray-900">Top Agents by Activity</h2>
                </div>
                {metrics?.top_agents && metrics.top_agents.length > 0 ? (
                  <div className="p-6 space-y-4">
                    {metrics.top_agents.map((agent, idx) => {
                      const maxTraces = Math.max(...metrics.top_agents.map(a => a.trace_count), 1);
                      return (
                        <div key={agent.id}>
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-sm font-medium text-gray-900">{agent.name}</span>
                            <span className="text-sm text-gray-500">{agent.trace_count} traces</span>
                          </div>
                          <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full bg-primary-500"
                              style={{ width: `${(agent.trace_count / maxTraces) * 100}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="px-6 py-8 text-center text-gray-500">
                    No agent activity yet
                  </div>
                )}
              </div>
            </div>

            {/* Span Type Breakdown */}
            {metrics?.span_type_breakdown && Object.keys(metrics.span_type_breakdown).length > 0 && (
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                <h2 className="font-semibold text-gray-900 mb-4">Span Type Breakdown</h2>
                <div className="flex flex-wrap gap-4">
                  {Object.entries(metrics.span_type_breakdown).map(([type, count]) => (
                    <div
                      key={type}
                      className="px-4 py-2 bg-gray-100 rounded-lg flex items-center gap-2"
                    >
                      <span className="font-medium text-gray-900">{type || "unknown"}</span>
                      <span className="text-gray-500">({count})</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </DashboardLayout>
  );
}
