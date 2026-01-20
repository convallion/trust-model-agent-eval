import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getToken(request: NextRequest): string | null {
  // Try to get token from Authorization header first
  const authHeader = request.headers.get("authorization");
  if (authHeader?.startsWith("Bearer ")) {
    return authHeader.substring(7);
  }
  // Fall back to cookie
  const cookieStore = cookies();
  return cookieStore.get("trustmodel_token")?.value || null;
}

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const agentId = searchParams.get("agent_id");
    const token = searchParams.get("token") || getToken(request);

    if (!agentId) {
      return NextResponse.json(
        { success: false, message: "agent_id is required" },
        { status: 400 }
      );
    }

    if (!token) {
      return NextResponse.json(
        { success: false, message: "Authentication required" },
        { status: 401 }
      );
    }

    const response = await fetch(
      `${API_BASE_URL}/v1/certificates?agent_id=${agentId}`,
      {
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
      }
    );

    if (!response.ok) {
      const error = await response.text();
      return NextResponse.json(
        { success: false, message: error },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json({ success: true, ...data });
  } catch (error: any) {
    console.error("Error fetching certificates:", error);
    return NextResponse.json(
      { success: false, message: error.message || "Failed to fetch certificates" },
      { status: 500 }
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { agent_id, evaluation_id, token: bodyToken } = body;
    const token = bodyToken || getToken(request);

    if (!agent_id || !evaluation_id) {
      return NextResponse.json(
        { success: false, message: "agent_id and evaluation_id are required" },
        { status: 400 }
      );
    }

    if (!token) {
      return NextResponse.json(
        { success: false, message: "Authentication required" },
        { status: 401 }
      );
    }

    const response = await fetch(`${API_BASE_URL}/v1/certificates`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ agent_id, evaluation_id }),
    });

    if (!response.ok) {
      const error = await response.text();
      let errorMessage = "Failed to issue certificate";
      try {
        const errorJson = JSON.parse(error);
        errorMessage = errorJson.detail || errorMessage;
      } catch {
        errorMessage = error || errorMessage;
      }
      return NextResponse.json(
        { success: false, message: errorMessage },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json({ success: true, certificate: data });
  } catch (error: any) {
    console.error("Error issuing certificate:", error);
    return NextResponse.json(
      { success: false, message: error.message || "Failed to issue certificate" },
      { status: 500 }
    );
  }
}
