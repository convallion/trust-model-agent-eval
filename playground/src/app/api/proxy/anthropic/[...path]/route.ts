import { NextRequest, NextResponse } from "next/server";

// Proxy endpoint for Anthropic API calls
// Users set ANTHROPIC_BASE_URL to point here and we capture all traces

const ANTHROPIC_API_URL = "https://api.anthropic.com";

export async function POST(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  const path = params.path.join("/");
  const agentId = request.headers.get("x-trustmodel-agent-id");

  // Get the original request body
  const body = await request.json();

  // Forward headers (except host)
  const headers: Record<string, string> = {};
  request.headers.forEach((value, key) => {
    if (!["host", "x-trustmodel-agent-id"].includes(key.toLowerCase())) {
      headers[key] = value;
    }
  });

  const startTime = Date.now();

  try {
    // Forward request to Anthropic
    const response = await fetch(`${ANTHROPIC_API_URL}/${path}`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });

    const responseData = await response.json();
    const endTime = Date.now();

    // Log trace to our backend if agent ID is provided
    if (agentId) {
      try {
        const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const token = request.headers.get("x-trustmodel-token");

        await fetch(`${backendUrl}/v1/traces`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            agent_id: agentId,
            name: `${body.model || "claude"} - ${path}`,
            started_at: new Date(startTime).toISOString(),
            ended_at: new Date(endTime).toISOString(),
            status: response.ok ? "ok" : "error",
            metadata: {
              provider: "anthropic",
              model: body.model,
              input_tokens: responseData.usage?.input_tokens,
              output_tokens: responseData.usage?.output_tokens,
              endpoint: path,
            },
            spans: [
              {
                span_id: crypto.randomUUID(),
                name: "llm_call",
                span_type: "llm_call",
                started_at: new Date(startTime).toISOString(),
                ended_at: new Date(endTime).toISOString(),
                status: response.ok ? "ok" : "error",
                attributes: {
                  model: body.model,
                  max_tokens: body.max_tokens,
                  input_messages: body.messages?.length || 0,
                  input_tokens: responseData.usage?.input_tokens,
                  output_tokens: responseData.usage?.output_tokens,
                  latency_ms: endTime - startTime,
                },
              },
            ],
          }),
        });
      } catch (traceError) {
        console.error("Failed to log trace:", traceError);
        // Don't fail the request if trace logging fails
      }
    }

    return NextResponse.json(responseData, {
      status: response.status,
      headers: {
        "x-trustmodel-traced": agentId ? "true" : "false",
      },
    });
  } catch (error: any) {
    console.error("Proxy error:", error);
    return NextResponse.json(
      { error: error.message || "Proxy request failed" },
      { status: 500 }
    );
  }
}

// Also handle GET requests (for some API endpoints)
export async function GET(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  const path = params.path.join("/");

  const headers: Record<string, string> = {};
  request.headers.forEach((value, key) => {
    if (key.toLowerCase() !== "host") {
      headers[key] = value;
    }
  });

  try {
    const response = await fetch(`${ANTHROPIC_API_URL}/${path}`, {
      method: "GET",
      headers,
    });

    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error: any) {
    return NextResponse.json(
      { error: error.message || "Proxy request failed" },
      { status: 500 }
    );
  }
}
