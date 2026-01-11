"use client";

import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { format } from "date-fns";
import {
  ArrowLeftIcon,
  ShieldCheckIcon,
  ExclamationTriangleIcon,
} from "@heroicons/react/24/outline";
import Link from "next/link";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { api } from "@/lib/api";
import { GradeBadge } from "@/components/ui/GradeBadge";
import { StatusBadge } from "@/components/ui/StatusBadge";

export default function CertificateDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();

  const { data: certificate, isLoading, error } = useQuery({
    queryKey: ["certificate", id],
    queryFn: () => api.getCertificate(id),
    enabled: !!id,
  });

  const revokeMutation = useMutation({
    mutationFn: (reason: string) => api.revokeCertificate(id, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["certificate", id] });
    },
  });

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
        </div>
      </DashboardLayout>
    );
  }

  if (error || !certificate) {
    return (
      <DashboardLayout>
        <div className="text-center py-12">
          <p className="text-red-600 mb-4">Failed to load certificate</p>
          <Link href="/certificates" className="text-primary-600 hover:underline">
            Back to certificates
          </Link>
        </div>
      </DashboardLayout>
    );
  }

  const isExpired = new Date(certificate.expires_at) < new Date();
  const isRevoked = certificate.status === "revoked";

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center gap-4">
          <Link
            href="/certificates"
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <ArrowLeftIcon className="h-5 w-5 text-gray-500" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              Trust Certificate
            </h1>
            <p className="text-sm text-gray-500">{certificate.agent_name}</p>
          </div>
        </div>

        {/* Warning banners */}
        {isRevoked && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3">
            <ExclamationTriangleIcon className="h-6 w-6 text-red-500 flex-shrink-0" />
            <div>
              <p className="font-medium text-red-800">Certificate Revoked</p>
              <p className="text-sm text-red-600">
                This certificate has been revoked and is no longer valid.
              </p>
            </div>
          </div>
        )}

        {isExpired && !isRevoked && (
          <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 flex items-start gap-3">
            <ExclamationTriangleIcon className="h-6 w-6 text-yellow-500 flex-shrink-0" />
            <div>
              <p className="font-medium text-yellow-800">Certificate Expired</p>
              <p className="text-sm text-yellow-600">
                This certificate has expired. Run a new evaluation to issue a fresh certificate.
              </p>
            </div>
          </div>
        )}

        {/* Main Content */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            {/* Certificate Card */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
              {/* Certificate Header */}
              <div
                className={`px-6 py-8 text-center ${
                  isRevoked
                    ? "bg-red-600"
                    : isExpired
                    ? "bg-gray-600"
                    : "bg-gradient-to-r from-primary-500 to-primary-600"
                }`}
              >
                <ShieldCheckIcon className="h-16 w-16 text-white/80 mx-auto mb-4" />
                <p className="text-white/80 text-sm mb-1">TrustModel Certificate</p>
                <h2 className="text-2xl font-bold text-white">
                  {certificate.agent_name}
                </h2>
                <div className="mt-4">
                  <GradeBadge grade={certificate.grade} size="lg" />
                </div>
              </div>

              {/* Certificate Body */}
              <div className="p-6">
                <dl className="grid grid-cols-2 gap-6">
                  <div>
                    <dt className="text-sm text-gray-500">Certificate ID</dt>
                    <dd className="font-mono text-sm text-gray-900 break-all">
                      {certificate.id}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-sm text-gray-500">Status</dt>
                    <dd>
                      <StatusBadge status={certificate.status} />
                    </dd>
                  </div>
                  <div>
                    <dt className="text-sm text-gray-500">Issued</dt>
                    <dd className="text-gray-900">
                      {format(new Date(certificate.issued_at), "PPpp")}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-sm text-gray-500">Expires</dt>
                    <dd className="text-gray-900">
                      {format(new Date(certificate.expires_at), "PPpp")}
                    </dd>
                  </div>
                </dl>
              </div>
            </div>

            {/* Scores */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Scores</h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center p-4 bg-gray-50 rounded-lg">
                  <p className="text-2xl font-bold text-gray-900">
                    {certificate.scores.overall.toFixed(1)}%
                  </p>
                  <p className="text-sm text-gray-500">Overall</p>
                </div>
                {certificate.scores.safety !== undefined && (
                  <div className="text-center p-4 bg-gray-50 rounded-lg">
                    <p className="text-2xl font-bold text-green-600">
                      {certificate.scores.safety.toFixed(1)}%
                    </p>
                    <p className="text-sm text-gray-500">Safety</p>
                  </div>
                )}
                {certificate.scores.capability !== undefined && (
                  <div className="text-center p-4 bg-gray-50 rounded-lg">
                    <p className="text-2xl font-bold text-blue-600">
                      {certificate.scores.capability.toFixed(1)}%
                    </p>
                    <p className="text-sm text-gray-500">Capability</p>
                  </div>
                )}
                {certificate.scores.reliability !== undefined && (
                  <div className="text-center p-4 bg-gray-50 rounded-lg">
                    <p className="text-2xl font-bold text-purple-600">
                      {certificate.scores.reliability.toFixed(1)}%
                    </p>
                    <p className="text-sm text-gray-500">Reliability</p>
                  </div>
                )}
              </div>
            </div>

            {/* Capabilities */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Capabilities
              </h2>
              {certificate.capabilities.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {certificate.capabilities.map((cap) => (
                    <span
                      key={cap}
                      className="inline-flex items-center rounded-full px-3 py-1 text-sm font-medium bg-green-100 text-green-700"
                    >
                      {cap}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-gray-500">No capabilities certified</p>
              )}

              {certificate.not_certified && certificate.not_certified.length > 0 && (
                <div className="mt-6">
                  <h3 className="text-sm font-medium text-gray-700 mb-2">
                    Not Certified
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {certificate.not_certified.map((cap) => (
                      <span
                        key={cap}
                        className="inline-flex items-center rounded-full px-3 py-1 text-sm font-medium bg-red-100 text-red-700"
                      >
                        {cap}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Actions */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Actions</h2>
              <div className="space-y-3">
                <Link
                  href={`/agents/${certificate.agent_id}`}
                  className="block w-full text-center px-4 py-2 text-sm font-medium text-primary-600 hover:bg-primary-50 rounded-lg border border-primary-200"
                >
                  View Agent
                </Link>
                {certificate.evaluation_id && (
                  <Link
                    href={`/evaluations/${certificate.evaluation_id}`}
                    className="block w-full text-center px-4 py-2 text-sm font-medium text-primary-600 hover:bg-primary-50 rounded-lg border border-primary-200"
                  >
                    View Evaluation
                  </Link>
                )}
                {!isRevoked && (
                  <button
                    onClick={() => {
                      const reason = prompt("Reason for revocation:");
                      if (reason) {
                        revokeMutation.mutate(reason);
                      }
                    }}
                    disabled={revokeMutation.isPending}
                    className="block w-full text-center px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50 rounded-lg border border-red-200 disabled:opacity-50"
                  >
                    {revokeMutation.isPending ? "Revoking..." : "Revoke Certificate"}
                  </button>
                )}
              </div>
            </div>

            {/* Signature */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Signature
              </h2>
              <div className="bg-gray-50 rounded-lg p-3">
                <code className="text-xs text-gray-600 break-all">
                  {certificate.signature || "No signature available"}
                </code>
              </div>
              <p className="mt-2 text-xs text-gray-500">
                Ed25519 signature verifying certificate authenticity
              </p>
            </div>

            {/* Verification */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Verification
              </h2>
              <pre className="bg-gray-50 rounded-lg p-3 text-xs overflow-x-auto">
{`curl -X GET \\
  http://localhost:8000/v1/certificates/${certificate.id}/verify`}
              </pre>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
