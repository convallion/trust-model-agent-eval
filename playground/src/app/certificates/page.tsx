"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { formatDistanceToNow, format } from "date-fns";
import { ShieldCheckIcon } from "@heroicons/react/24/outline";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { api } from "@/lib/api";
import { GradeBadge } from "@/components/ui/GradeBadge";
import { StatusBadge } from "@/components/ui/StatusBadge";

export default function CertificatesPage() {
  const { data: certificates, isLoading } = useQuery({
    queryKey: ["certificates"],
    queryFn: () => api.getCertificates(),
  });

  return (
    <DashboardLayout>
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Certificates</h1>
        <p className="mt-1 text-sm text-gray-500">
          Trust certificates issued to your agents
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {isLoading ? (
          <div className="col-span-full text-center py-8 text-gray-500">
            Loading certificates...
          </div>
        ) : certificates?.items.length === 0 ? (
          <div className="col-span-full bg-white rounded-xl shadow-sm border border-gray-200 p-8 text-center">
            <ShieldCheckIcon className="h-12 w-12 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500 mb-2">No certificates issued yet.</p>
            <p className="text-sm text-gray-400">
              Run evaluations on your agents to issue trust certificates.
            </p>
          </div>
        ) : (
          certificates?.items.map((cert) => (
            <Link
              key={cert.id}
              href={`/certificates/${cert.id}`}
              className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden card-hover"
            >
              {/* Certificate Header */}
              <div className="bg-gradient-to-r from-primary-500 to-primary-600 px-6 py-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <ShieldCheckIcon className="h-8 w-8 text-white/80" />
                    <div>
                      <p className="text-sm text-white/80">Trust Certificate</p>
                      <p className="font-semibold text-white">
                        {cert.agent_name}
                      </p>
                    </div>
                  </div>
                  <GradeBadge grade={cert.grade} size="lg" />
                </div>
              </div>

              {/* Certificate Body */}
              <div className="p-6">
                <div className="flex justify-between items-center mb-4">
                  <StatusBadge status={cert.status} />
                  <span className="text-sm text-gray-500">
                    Score: {cert.scores.overall.toFixed(1)}%
                  </span>
                </div>

                {/* Scores breakdown */}
                <div className="space-y-2 mb-4">
                  {cert.scores.safety !== undefined && (
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-500">Safety</span>
                      <span className="font-medium">
                        {cert.scores.safety.toFixed(1)}%
                      </span>
                    </div>
                  )}
                  {cert.scores.capability !== undefined && (
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-500">Capability</span>
                      <span className="font-medium">
                        {cert.scores.capability.toFixed(1)}%
                      </span>
                    </div>
                  )}
                </div>

                {/* Capabilities */}
                {cert.capabilities.length > 0 && (
                  <div className="mb-4">
                    <p className="text-xs text-gray-500 mb-1">Capabilities</p>
                    <div className="flex flex-wrap gap-1">
                      {cert.capabilities.slice(0, 3).map((cap) => (
                        <span
                          key={cap}
                          className="inline-flex items-center rounded px-2 py-0.5 text-xs font-medium bg-green-100 text-green-700"
                        >
                          {cap}
                        </span>
                      ))}
                      {cert.capabilities.length > 3 && (
                        <span className="text-xs text-gray-400">
                          +{cert.capabilities.length - 3} more
                        </span>
                      )}
                    </div>
                  </div>
                )}

                {/* Footer */}
                <div className="pt-4 border-t border-gray-100 flex justify-between text-xs text-gray-500">
                  <span>Issued {format(new Date(cert.issued_at), "MMM d, yyyy")}</span>
                  <span>
                    Expires {format(new Date(cert.expires_at), "MMM d, yyyy")}
                  </span>
                </div>
              </div>
            </Link>
          ))
        )}
      </div>
    </div>
    </DashboardLayout>
  );
}
