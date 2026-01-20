import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  try {
    const { url, apiKey, limit = 20 } = await request.json();

    if (!url) {
      return NextResponse.json(
        { success: false, message: "URL is required" },
        { status: 400 }
      );
    }

    // Clean URL - remove trailing slash
    const baseUrl = url.replace(/\/$/, "");

    // LangGraph Cloud requires these specific headers
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };

    if (apiKey) {
      headers["X-Auth-Scheme"] = "langsmith-api-key";
      headers["x-api-key"] = apiKey;
    }

    // LangGraph uses POST /threads/search (not GET /threads)
    const searchUrl = `${baseUrl}/threads/search`;
    console.log(`Fetching threads from: ${searchUrl}`);

    const threadsResponse = await fetch(searchUrl, {
      method: "POST",
      headers,
      body: JSON.stringify({ limit }),
      signal: AbortSignal.timeout(15000),
    });

    if (!threadsResponse.ok) {
      const errorText = await threadsResponse.text();
      console.log(`Error: ${threadsResponse.status} - ${errorText}`);
      return NextResponse.json({
        success: false,
        message: `API error: ${threadsResponse.status}. ${errorText.slice(0, 100)}`,
      }, { status: 400 });
    }

    const threads = await threadsResponse.json();
    console.log(`Found ${threads.length} threads`);

    // If no threads, return success with empty array (not an error)
    if (!Array.isArray(threads) || threads.length === 0) {
      return NextResponse.json({
        success: true,
        traces: [],
        total: 0,
        message: "No conversations yet. Start chatting with your agent to see traces here.",
      });
    }

    // Get details for each thread
    const tracesWithDetails = await Promise.all(
      threads.slice(0, limit).map(async (thread: any) => {
        const threadId = thread.thread_id || thread.id;

        // Get thread state for messages
        let messages: any[] = [];
        let lastMessage: string | null = null;

        try {
          const stateResponse = await fetch(
            `${baseUrl}/threads/${threadId}/state`,
            {
              method: "GET",
              headers,
              signal: AbortSignal.timeout(10000),
            }
          );

          if (stateResponse.ok) {
            const state = await stateResponse.json();
            messages = state?.values?.messages || [];
            lastMessage = getLastMessage(messages);
          }
        } catch (e) {
          // State might not be available
        }

        return {
          id: threadId,
          created_at: thread.created_at,
          updated_at: thread.updated_at,
          metadata: thread.metadata || {},
          status: thread.status || "idle",
          runs: [],
          messages,
          lastMessage,
        };
      })
    );

    return NextResponse.json({
      success: true,
      traces: tracesWithDetails,
      total: threads.length,
    });
  } catch (error: any) {
    console.error("Fetch traces error:", error);
    return NextResponse.json(
      {
        success: false,
        message: error.message || "Failed to fetch traces",
      },
      { status: 500 }
    );
  }
}

function getLastMessage(messages: any[]): string | null {
  if (!messages || messages.length === 0) return null;
  const lastMsg = messages[messages.length - 1];
  if (typeof lastMsg.content === "string") {
    return lastMsg.content.slice(0, 200);
  }
  if (Array.isArray(lastMsg.content)) {
    const textPart = lastMsg.content.find((p: any) => p.type === "text");
    return textPart?.text?.slice(0, 200) || null;
  }
  return null;
}
