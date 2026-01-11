"use client";

import {
  CpuChipIcon,
  ChartBarIcon,
  ShieldCheckIcon,
  DocumentTextIcon,
} from "@heroicons/react/24/outline";
import type { DashboardStats } from "@/lib/api";

interface StatsCardsProps {
  stats: DashboardStats | null;
}

export function StatsCards({ stats }: StatsCardsProps) {
  const cards = [
    {
      name: "Total Agents",
      value: stats?.total_agents || 0,
      subtext: `${stats?.active_agents || 0} active in last 24h`,
      icon: CpuChipIcon,
      color: "bg-blue-500",
    },
    {
      name: "Total Traces",
      value: stats?.total_traces || 0,
      subtext: "Interactions recorded",
      icon: DocumentTextIcon,
      color: "bg-purple-500",
    },
    {
      name: "Evaluations",
      value: stats?.total_evaluations || 0,
      subtext: `${stats?.completed_evaluations || 0} completed`,
      icon: ChartBarIcon,
      color: "bg-indigo-500",
    },
    {
      name: "Certificates",
      value: stats?.active_certificates || 0,
      subtext: stats?.avg_trust_score
        ? `Avg score: ${stats.avg_trust_score.toFixed(1)}`
        : "No certificates yet",
      icon: ShieldCheckIcon,
      color: "bg-green-500",
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((card) => (
        <div
          key={card.name}
          className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 card-hover"
        >
          <div className="flex items-center">
            <div className={`${card.color} rounded-lg p-3`}>
              <card.icon className="h-6 w-6 text-white" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">{card.name}</p>
              <p className="text-2xl font-bold text-gray-900">{card.value}</p>
            </div>
          </div>
          <div className="mt-4">
            <span className="text-sm text-gray-500">{card.subtext}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
