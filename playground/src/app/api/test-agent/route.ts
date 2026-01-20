import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  try {
    const { url, apiKey } = await request.json();

    if (!url) {
      return NextResponse.json(
        { success: false, message: "URL is required" },
        { status: 400 }
      );
    }

    // Try to connect to the LangGraph API
    // LangGraph APIs typically have a /info or /assistants endpoint
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };

    if (apiKey) {
      headers["X-Auth-Scheme"] = "langsmith-api-key";
      headers["x-api-key"] = apiKey;
    }

    // Try multiple endpoints to verify the agent
    const endpoints = ["/info", "/assistants", "/threads"];
    let connected = false;
    let details = "";

    for (const endpoint of endpoints) {
      try {
        const response = await fetch(`${url}${endpoint}`, {
          method: "GET",
          headers,
          signal: AbortSignal.timeout(10000), // 10 second timeout
        });

        if (response.ok) {
          connected = true;
          const data = await response.json();
          details = `Connected via ${endpoint}`;

          // Try to get assistant info if available
          if (endpoint === "/assistants" && Array.isArray(data)) {
            details = `Found ${data.length} assistant(s)`;
          }
          break;
        }
      } catch (e) {
        // Try next endpoint
        continue;
      }
    }

    if (!connected) {
      // Try creating a thread as a final test
      try {
        const response = await fetch(`${url}/threads`, {
          method: "POST",
          headers,
          signal: AbortSignal.timeout(10000),
        });

        if (response.ok || response.status === 201) {
          connected = true;
          details = "Agent is responding";
        }
      } catch (e) {
        // Connection failed
      }
    }

    if (connected) {
      return NextResponse.json({
        success: true,
        message: "Connection successful",
        details,
      });
    } else {
      return NextResponse.json(
        {
          success: false,
          message: "Could not connect to agent. Please check the URL and try again.",
        },
        { status: 400 }
      );
    }
  } catch (error: any) {
    return NextResponse.json(
      {
        success: false,
        message: error.message || "Connection test failed",
      },
      { status: 500 }
    );
  }
}
