import { NextRequest, NextResponse } from "next/server";

// Chat with a LangGraph agent
export async function POST(request: NextRequest) {
  try {
    const { url, apiKey, message, threadId } = await request.json();

    if (!url || !message) {
      return NextResponse.json(
        { success: false, message: "URL and message are required" },
        { status: 400 }
      );
    }

    const baseUrl = url.replace(/\/$/, "");

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };

    if (apiKey) {
      headers["X-Auth-Scheme"] = "langsmith-api-key";
      headers["x-api-key"] = apiKey;
    }

    // Create a new thread if not provided
    let currentThreadId = threadId;
    if (!currentThreadId) {
      const threadResponse = await fetch(`${baseUrl}/threads`, {
        method: "POST",
        headers,
        body: JSON.stringify({}),
        signal: AbortSignal.timeout(15000),
      });

      if (!threadResponse.ok) {
        const error = await threadResponse.text();
        return NextResponse.json({
          success: false,
          message: `Failed to create thread: ${error.slice(0, 100)}`,
        }, { status: 400 });
      }

      const thread = await threadResponse.json();
      currentThreadId = thread.thread_id;
    }

    // Send message to the agent
    const runResponse = await fetch(
      `${baseUrl}/threads/${currentThreadId}/runs`,
      {
        method: "POST",
        headers,
        body: JSON.stringify({
          assistant_id: "agent", // Default assistant ID
          input: {
            messages: [
              {
                role: "user",
                content: message,
              },
            ],
          },
        }),
        signal: AbortSignal.timeout(60000), // 60s timeout for agent response
      }
    );

    if (!runResponse.ok) {
      const error = await runResponse.text();
      return NextResponse.json({
        success: false,
        message: `Failed to send message: ${error.slice(0, 100)}`,
      }, { status: 400 });
    }

    const run = await runResponse.json();

    // Wait for run to complete and get the response
    let attempts = 0;
    const maxAttempts = 30; // 30 seconds max wait
    let finalState = null;

    while (attempts < maxAttempts) {
      await new Promise((resolve) => setTimeout(resolve, 1000));

      const stateResponse = await fetch(
        `${baseUrl}/threads/${currentThreadId}/state`,
        {
          method: "GET",
          headers,
          signal: AbortSignal.timeout(10000),
        }
      );

      if (stateResponse.ok) {
        const state = await stateResponse.json();
        const messages = state?.values?.messages || [];

        // Check if we have a response (more than just the user message)
        if (messages.length > 0) {
          const lastMessage = messages[messages.length - 1];
          if (lastMessage.type === "ai" || lastMessage.role === "assistant") {
            finalState = state;
            break;
          }
        }
      }

      attempts++;
    }

    if (!finalState) {
      return NextResponse.json({
        success: true,
        threadId: currentThreadId,
        message: "Message sent, but response is still processing",
        response: null,
      });
    }

    const messages = finalState.values?.messages || [];
    const lastMessage = messages[messages.length - 1];
    let responseText = "";

    if (typeof lastMessage?.content === "string") {
      responseText = lastMessage.content;
    } else if (Array.isArray(lastMessage?.content)) {
      const textPart = lastMessage.content.find((p: any) => p.type === "text");
      responseText = textPart?.text || "";
    }

    return NextResponse.json({
      success: true,
      threadId: currentThreadId,
      response: responseText,
      messages: messages.map((m: any) => ({
        role: m.type === "human" ? "user" : m.type === "ai" ? "assistant" : m.role || m.type,
        content: typeof m.content === "string" ? m.content : JSON.stringify(m.content),
      })),
    });
  } catch (error: any) {
    console.error("Chat error:", error);
    return NextResponse.json(
      {
        success: false,
        message: error.message || "Failed to chat with agent",
      },
      { status: 500 }
    );
  }
}
