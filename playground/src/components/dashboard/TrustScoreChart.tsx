"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { Evaluation } from "@/lib/api";

interface TrustScoreChartProps {
  evaluations: Evaluation[];
}

export function TrustScoreChart({ evaluations }: TrustScoreChartProps) {
  // Transform evaluations into chart data
  const chartData = evaluations
    .filter((e) => e.status === "completed" && e.scores)
    .slice(0, 10)
    .reverse()
    .map((e, index) => ({
      name: `Eval ${index + 1}`,
      overall: e.scores?.overall || 0,
      safety: e.scores?.safety || 0,
      capability: e.scores?.capability || 0,
    }));

  // Add sample data if no evaluations
  const data =
    chartData.length > 0
      ? chartData
      : [
          { name: "Week 1", overall: 75, safety: 80, capability: 70 },
          { name: "Week 2", overall: 78, safety: 82, capability: 74 },
          { name: "Week 3", overall: 82, safety: 85, capability: 78 },
          { name: "Week 4", overall: 85, safety: 88, capability: 82 },
          { name: "Week 5", overall: 87, safety: 90, capability: 84 },
        ];

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">
        Trust Score Trend
      </h2>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={data}
            margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
          >
            <defs>
              <linearGradient id="colorOverall" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="colorSafety" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis
              dataKey="name"
              axisLine={false}
              tickLine={false}
              tick={{ fill: "#94a3b8", fontSize: 12 }}
            />
            <YAxis
              domain={[0, 100]}
              axisLine={false}
              tickLine={false}
              tick={{ fill: "#94a3b8", fontSize: 12 }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#fff",
                border: "1px solid #e2e8f0",
                borderRadius: "8px",
                boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
              }}
            />
            <Area
              type="monotone"
              dataKey="overall"
              stroke="#0ea5e9"
              fillOpacity={1}
              fill="url(#colorOverall)"
              strokeWidth={2}
              name="Overall"
            />
            <Area
              type="monotone"
              dataKey="safety"
              stroke="#10b981"
              fillOpacity={1}
              fill="url(#colorSafety)"
              strokeWidth={2}
              name="Safety"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <div className="flex justify-center gap-6 mt-4">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-primary-500" />
          <span className="text-sm text-gray-600">Overall Score</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-green-500" />
          <span className="text-sm text-gray-600">Safety Score</span>
        </div>
      </div>
    </div>
  );
}
