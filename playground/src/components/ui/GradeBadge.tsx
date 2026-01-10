"use client";

import clsx from "clsx";

interface GradeBadgeProps {
  grade: string;
  size?: "sm" | "md" | "lg";
}

export function GradeBadge({ grade, size = "md" }: GradeBadgeProps) {
  const sizeClasses = {
    sm: "w-8 h-8 text-sm",
    md: "w-10 h-10 text-lg",
    lg: "w-14 h-14 text-2xl",
  };

  const gradeColors: Record<string, string> = {
    A: "bg-green-100 text-green-800 ring-green-600/20",
    B: "bg-blue-100 text-blue-800 ring-blue-600/20",
    C: "bg-yellow-100 text-yellow-800 ring-yellow-600/20",
    D: "bg-orange-100 text-orange-800 ring-orange-600/20",
    F: "bg-red-100 text-red-800 ring-red-600/20",
  };

  return (
    <div
      className={clsx(
        "inline-flex items-center justify-center rounded-full font-bold ring-1 ring-inset",
        sizeClasses[size],
        gradeColors[grade] || "bg-gray-100 text-gray-800 ring-gray-600/20"
      )}
    >
      {grade}
    </div>
  );
}
