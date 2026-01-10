"use client";

import { useQuery } from "@tanstack/react-query";
import { StatsCards } from "@/components/dashboard/StatsCards";
import { RecentAgents } from "@/components/dashboard/RecentAgents";
import { RecentEvaluations } from "@/components/dashboard/RecentEvaluations";
import { TrustScoreChart } from "@/components/dashboard/TrustScoreChart";
import { api } from "@/lib/api";

export default function Dashboard() {
  const { data: agents } = useQuery({
    queryKey: ["agents"],
    queryFn: () => api.getAgents(),
  });

  const { data: evaluations } = useQuery({
    queryKey: ["evaluations"],
    queryFn: () => api.getEvaluations(),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="mt-1 text-sm text-gray-500">
          Monitor your agents and their trust status
        </p>
      </div>

      <StatsCards
        agents={agents?.items || []}
        evaluations={evaluations?.items || []}
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <TrustScoreChart evaluations={evaluations?.items || []} />
        <RecentEvaluations evaluations={evaluations?.items || []} />
      </div>

      <RecentAgents agents={agents?.items || []} />
    </div>
  );
}
