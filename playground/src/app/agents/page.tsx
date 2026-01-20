"use client";

import { redirect } from "next/navigation";

// Redirect to home page - agents are shown there
export default function AgentsPage() {
  redirect("/");
}
