import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const body = await request.json();
    const { reason } = body;

    if (!reason || reason.length < 10) {
      return NextResponse.json(
        { success: false, message: "Reason must be at least 10 characters" },
        { status: 400 }
      );
    }

    const response = await fetch(
      `${API_BASE_URL}/v1/certificates/${params.id}/revoke`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${process.env.API_TOKEN || "dev-token"}`,
        },
        body: JSON.stringify({ reason }),
      }
    );

    if (!response.ok) {
      const error = await response.text();
      let errorMessage = "Failed to revoke certificate";
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
    console.error("Error revoking certificate:", error);
    return NextResponse.json(
      { success: false, message: error.message || "Failed to revoke certificate" },
      { status: 500 }
    );
  }
}
