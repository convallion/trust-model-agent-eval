"use client";

import {
  CpuChipIcon,
  ChartBarIcon,
  ShieldCheckIcon,
  ExclamationTriangleIcon,
} from "@heroicons/react/24/outline";
import type { Agent, Evaluation } from "@/lib/api";

interface StatsCardsProps {
  agents: Agent[];
  evaluations: Evaluation[];
}

export function StatsCards({ agents, evaluations }: StatsCardsProps) {
  const activeAgents = agents.filter((a) => a.status === "active").length;
  const completedEvals = evaluations.filter(
    (e) => e.status === "completed"
  ).length;
  const certifiedAgents = agents.filter(
    (a) => a.stats?.latest_certificate_grade
  ).length;
  const failedEvals = evaluations.filter((e) => e.status === "failed").length;

  const stats = [
    {
      name: "Active Agents",
      value: activeAgents,
      icon: CpuChipIcon,
      color: "bg-blue-500",
      change: "+2 this week",
      changeType: "positive" as const,
    },
    {
      name: "Evaluations Run",
      value: completedEvals,
      icon: ChartBarIcon,
      color: "bg-purple-500",
      change: "+12 this week",
      changeType: "positive" as const,
    },
    {
      name: "Certified Agents",
      value: certifiedAgents,
      icon: ShieldCheckIcon,
      color: "bg-green-500",
      change: "+1 this week",
      changeType: "positive" as const,
    },
    {
      name: "Failed Evaluations",
      value: failedEvals,
      icon: ExclamationTriangleIcon,
      color: "bg-red-500",
      change: failedEvals > 0 ? "Needs attention" : "All passing",
      changeType: failedEvals > 0 ? ("negative" as const) : ("positive" as const),
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
      {stats.map((stat) => (
        <div
          key={stat.name}
          className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 card-hover"
        >
          <div className="flex items-center">
            <div className={`${stat.color} rounded-lg p-3`}>
              <stat.icon className="h-6 w-6 text-white" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">{stat.name}</p>
              <p className="text-2xl font-bold text-gray-900">{stat.value}</p>
            </div>
          </div>
          <div className="mt-4">
            <span
              className={`text-sm ${
                stat.changeType === "positive"
                  ? "text-green-600"
                  : "text-red-600"
              }`}
            >
              {stat.change}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
