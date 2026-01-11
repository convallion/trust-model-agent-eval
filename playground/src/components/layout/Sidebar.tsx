"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import {
  HomeIcon,
  CpuChipIcon,
  ChartBarIcon,
  ShieldCheckIcon,
  DocumentTextIcon,
  Cog6ToothIcon,
  ChatBubbleLeftRightIcon,
  EyeIcon,
  CommandLineIcon,
} from "@heroicons/react/24/outline";
import { api } from "@/lib/api";

const navigation = [
  { name: "Dashboard", href: "/", icon: HomeIcon },
  { name: "Playground", href: "/playground", icon: ChatBubbleLeftRightIcon },
  { name: "Terminal", href: "/terminal", icon: CommandLineIcon },
  { name: "Observability", href: "/observability", icon: EyeIcon },
  { name: "Agents", href: "/agents", icon: CpuChipIcon },
  { name: "Traces", href: "/traces", icon: DocumentTextIcon },
  { name: "Evaluations", href: "/evaluations", icon: ChartBarIcon },
  { name: "Certificates", href: "/certificates", icon: ShieldCheckIcon },
  { name: "Settings", href: "/settings", icon: Cog6ToothIcon },
];

export function Sidebar() {
  const pathname = usePathname();

  const { data: stats } = useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: () => api.getDashboardStats(),
    staleTime: 30000, // Cache for 30 seconds
  });

  return (
    <div className="hidden lg:flex lg:flex-shrink-0">
      <div className="flex w-64 flex-col">
        <div className="flex min-h-0 flex-1 flex-col bg-white border-r border-gray-200">
          {/* Logo */}
          <div className="flex h-16 flex-shrink-0 items-center px-4 border-b border-gray-200">
            <div className="flex items-center gap-2">
              <ShieldCheckIcon className="h-8 w-8 text-primary-600" />
              <span className="text-xl font-bold text-gray-900">
                TrustModel
              </span>
            </div>
          </div>

          {/* Navigation */}
          <div className="flex flex-1 flex-col overflow-y-auto pt-5 pb-4">
            <nav className="flex-1 space-y-1 px-2">
              {navigation.map((item) => {
                const isActive =
                  pathname === item.href ||
                  (item.href !== "/" && pathname.startsWith(item.href));

                return (
                  <Link
                    key={item.name}
                    href={item.href}
                    className={clsx(
                      isActive
                        ? "bg-primary-50 text-primary-700"
                        : "text-gray-600 hover:bg-gray-50 hover:text-gray-900",
                      "group flex items-center rounded-lg px-3 py-2 text-sm font-medium transition-colors"
                    )}
                  >
                    <item.icon
                      className={clsx(
                        isActive
                          ? "text-primary-600"
                          : "text-gray-400 group-hover:text-gray-500",
                        "mr-3 h-5 w-5 flex-shrink-0 transition-colors"
                      )}
                    />
                    {item.name}
                  </Link>
                );
              })}
            </nav>
          </div>

          {/* Trust Score */}
          <div className="flex-shrink-0 p-4 border-t border-gray-200">
            <div className="rounded-lg bg-gradient-to-r from-primary-500 to-primary-600 p-4 text-white">
              <p className="text-sm font-medium opacity-90">
                Organization Trust Score
              </p>
              <p className="mt-1 text-3xl font-bold">
                {stats?.avg_trust_score
                  ? stats.avg_trust_score.toFixed(1)
                  : "--"}
              </p>
              <div className="mt-2 flex items-center gap-1 text-sm opacity-80">
                <span className="inline-block w-2 h-2 bg-green-300 rounded-full" />
                <span>
                  {stats?.active_certificates || 0} agent
                  {stats?.active_certificates !== 1 ? "s" : ""} certified
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
