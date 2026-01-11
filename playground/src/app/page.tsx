"use client";

import { useQuery } from "@tanstack/react-query";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { StatsCards } from "@/components/dashboard/StatsCards";
import { RecentAgents } from "@/components/dashboard/RecentAgents";
import { RecentEvaluations } from "@/components/dashboard/RecentEvaluations";
import { TrustScoreChart } from "@/components/dashboard/TrustScoreChart";
import { api } from "@/lib/api";

export default function Dashboard() {
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: () => api.getDashboardStats(),
  });

  const { data: agents, isLoading: agentsLoading } = useQuery({
    queryKey: ["agents"],
    queryFn: () => api.getAgents(),
  });

  const { data: evaluations, isLoading: evalsLoading } = useQuery({
    queryKey: ["evaluations"],
    queryFn: () => api.getEvaluations(),
  });

  const isLoading = statsLoading || agentsLoading || evalsLoading;

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="mt-1 text-sm text-gray-500">
            Monitor your agents and their trust status
          </p>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
          </div>
        ) : (
          <>
            <StatsCards stats={stats || null} />

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <TrustScoreChart evaluations={evaluations?.items || []} />
              <RecentEvaluations evaluations={evaluations?.items || []} />
            </div>

            <RecentAgents agents={agents?.items || []} />
          </>
        )}
      </div>
    </DashboardLayout>
  );
}
