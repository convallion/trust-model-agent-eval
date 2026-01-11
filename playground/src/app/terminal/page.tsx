"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import {
  CommandLineIcon,
  XMarkIcon,
  PlusIcon,
  SignalIcon,
  SignalSlashIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
} from "@heroicons/react/24/outline";

// Dynamic import to avoid SSR issues
let Terminal: typeof import("@xterm/xterm").Terminal | null = null;
let FitAddon: typeof import("@xterm/addon-fit").FitAddon | null = null;
let WebLinksAddon: typeof import("@xterm/addon-web-links").WebLinksAddon | null = null;

interface TerminalTab {
  id: string;
  name: string;
  ws: WebSocket | null;
  terminal: InstanceType<typeof import("@xterm/xterm").Terminal> | null;
  fitAddon: InstanceType<typeof import("@xterm/addon-fit").FitAddon> | null;
}

interface TraceEvent {
  id: string;
  type: "trace_started" | "span_added" | "trace_completed" | "connected" | "ping";
  data?: {
    trace_id?: string;
    agent_id?: string;
    agent_name?: string;
    span_id?: string;
    span_type?: string;
    name?: string;
    status?: string;
    success?: boolean;
    duration_ms?: number;
    attributes?: Record<string, unknown>;
  };
  timestamp: string;
}

interface ActiveTrace {
  id: string;
  agent_name: string;
  started_at: string;
  spans: TraceEvent[];
  completed: boolean;
  success?: boolean;
  duration_ms?: number;
}

export default function TerminalPage() {
  const [tabs, setTabs] = useState<TerminalTab[]>([]);
  const [activeTabId, setActiveTabId] = useState<string | null>(null);
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const terminalRef = useRef<HTMLDivElement>(null);
  const [isLoaded, setIsLoaded] = useState(false);

  // Trace streaming state
  const [traceWs, setTraceWs] = useState<WebSocket | null>(null);
  const [traceConnected, setTraceConnected] = useState(false);
  const [activeTraces, setActiveTraces] = useState<Map<string, ActiveTrace>>(new Map());
  const [showTracePanel, setShowTracePanel] = useState(true);
  const [tracePanelWidth, setTracePanelWidth] = useState(400);

  // Load xterm dynamically on client side
  useEffect(() => {
    async function loadXterm() {
      const xtermModule = await import("@xterm/xterm");
      const fitModule = await import("@xterm/addon-fit");
      const webLinksModule = await import("@xterm/addon-web-links");

      Terminal = xtermModule.Terminal;
      FitAddon = fitModule.FitAddon;
      WebLinksAddon = webLinksModule.WebLinksAddon;

      setIsLoaded(true);
    }
    loadXterm();
  }, []);

  // Load CSS
  useEffect(() => {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "https://cdn.jsdelivr.net/npm/@xterm/xterm@5.5.0/css/xterm.min.css";
    document.head.appendChild(link);
    return () => {
      document.head.removeChild(link);
    };
  }, []);

  // Connect to trace stream WebSocket
  const connectTraceStream = useCallback(() => {
    const token = localStorage.getItem("trustmodel_token");
    if (!token) return;

    const wsUrl = `${process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000"}/v1/traces/stream?token=${token}`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setTraceConnected(true);
      console.log("Trace stream connected");
    };

    ws.onmessage = (event) => {
      try {
        const message: TraceEvent = JSON.parse(event.data);
        message.id = `${Date.now()}-${Math.random()}`;

        if (message.type === "ping") {
          ws.send(JSON.stringify({ type: "pong" }));
          return;
        }

        if (message.type === "connected") {
          return;
        }

        // Handle trace events
        setActiveTraces((prev) => {
          const newMap = new Map(prev);

          if (message.type === "trace_started" && message.data) {
            newMap.set(message.data.trace_id!, {
              id: message.data.trace_id!,
              agent_name: message.data.agent_name || "Unknown",
              started_at: message.timestamp,
              spans: [],
              completed: false,
            });
          } else if (message.type === "span_added" && message.data) {
            const trace = newMap.get(message.data.trace_id!);
            if (trace) {
              trace.spans.push(message);
            } else {
              // Create trace if we missed the start event
              newMap.set(message.data.trace_id!, {
                id: message.data.trace_id!,
                agent_name: "Unknown",
                started_at: message.timestamp,
                spans: [message],
                completed: false,
              });
            }
          } else if (message.type === "trace_completed" && message.data) {
            const trace = newMap.get(message.data.trace_id!);
            if (trace) {
              trace.completed = true;
              trace.success = message.data.success;
              trace.duration_ms = message.data.duration_ms;
            }
          }

          // Keep only last 20 traces
          if (newMap.size > 20) {
            const entries = Array.from(newMap.entries());
            entries.slice(0, entries.length - 20).forEach(([key]) => newMap.delete(key));
          }

          return newMap;
        });
      } catch (e) {
        console.error("Failed to parse trace event:", e);
      }
    };

    ws.onerror = () => {
      setTraceConnected(false);
    };

    ws.onclose = () => {
      setTraceConnected(false);
      // Reconnect after 3 seconds
      setTimeout(() => {
        const token = localStorage.getItem("trustmodel_token");
        if (token) {
          connectTraceStream();
        }
      }, 3000);
    };

    setTraceWs(ws);
  }, []);

  // Connect to trace stream on mount
  useEffect(() => {
    connectTraceStream();
    return () => {
      traceWs?.close();
    };
  }, []);

  const activeTab = tabs.find((t) => t.id === activeTabId);

  // Mount/unmount terminal when tab changes
  useEffect(() => {
    if (!isLoaded || !terminalRef.current) return;

    // Clear existing content
    terminalRef.current.innerHTML = "";

    if (activeTab?.terminal) {
      activeTab.terminal.open(terminalRef.current);
      activeTab.fitAddon?.fit();
      activeTab.terminal.focus();
    }
  }, [activeTabId, isLoaded, activeTab]);

  // Handle window resize
  useEffect(() => {
    const handleResize = () => {
      if (activeTab?.fitAddon && activeTab.terminal) {
        activeTab.fitAddon.fit();
        // Send resize to server
        if (activeTab.ws?.readyState === WebSocket.OPEN) {
          activeTab.ws.send(
            JSON.stringify({
              type: "resize",
              rows: activeTab.terminal.rows,
              cols: activeTab.terminal.cols,
            })
          );
        }
      }
    };

    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [activeTab]);

  // Refit terminal when panel width changes
  useEffect(() => {
    if (activeTab?.fitAddon) {
      setTimeout(() => {
        activeTab.fitAddon?.fit();
      }, 100);
    }
  }, [showTracePanel, tracePanelWidth, activeTab]);

  const createNewTerminal = async () => {
    if (!Terminal || !FitAddon || !WebLinksAddon) return;

    setIsConnecting(true);
    setError(null);

    const token = localStorage.getItem("trustmodel_token");
    if (!token) {
      setError("Not authenticated. Please log in.");
      setIsConnecting(false);
      return;
    }

    const tabId = `term-${Date.now()}`;
    const tabNumber = tabs.length + 1;

    // Create terminal instance
    const terminal = new Terminal({
      cursorBlink: true,
      cursorStyle: "block",
      fontFamily:
        "'JetBrains Mono', 'Fira Code', 'Cascadia Code', Menlo, Monaco, 'Courier New', monospace",
      fontSize: 14,
      lineHeight: 1.2,
      theme: {
        background: "#1e1e2e",
        foreground: "#cdd6f4",
        cursor: "#f5e0dc",
        cursorAccent: "#1e1e2e",
        selectionBackground: "#585b70",
        selectionForeground: "#cdd6f4",
        black: "#45475a",
        red: "#f38ba8",
        green: "#a6e3a1",
        yellow: "#f9e2af",
        blue: "#89b4fa",
        magenta: "#f5c2e7",
        cyan: "#94e2d5",
        white: "#bac2de",
        brightBlack: "#585b70",
        brightRed: "#f38ba8",
        brightGreen: "#a6e3a1",
        brightYellow: "#f9e2af",
        brightBlue: "#89b4fa",
        brightMagenta: "#f5c2e7",
        brightCyan: "#94e2d5",
        brightWhite: "#a6adc8",
      },
    });

    const fitAddon = new FitAddon();
    const webLinksAddon = new WebLinksAddon();

    terminal.loadAddon(fitAddon);
    terminal.loadAddon(webLinksAddon);

    // Connect to WebSocket
    const wsUrl = `${process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000"}/v1/terminal?token=${token}`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setIsConnecting(false);

      // Send initial resize
      setTimeout(() => {
        fitAddon.fit();
        ws.send(
          JSON.stringify({
            type: "resize",
            rows: terminal.rows,
            cols: terminal.cols,
          })
        );
      }, 100);
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === "output") {
          terminal.write(message.data);
        } else if (message.type === "error") {
          terminal.write(`\r\n\x1b[31mError: ${message.message}\x1b[0m\r\n`);
        }
      } catch {
        // Raw output
        terminal.write(event.data);
      }
    };

    ws.onerror = () => {
      setError("Connection error. Make sure the server is running.");
      setIsConnecting(false);
    };

    ws.onclose = () => {
      terminal.write("\r\n\x1b[33mConnection closed.\x1b[0m\r\n");
    };

    // Handle terminal input
    terminal.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "input", data }));
      }
    });

    const newTab: TerminalTab = {
      id: tabId,
      name: `Terminal ${tabNumber}`,
      ws,
      terminal,
      fitAddon,
    };

    setTabs((prev) => [...prev, newTab]);
    setActiveTabId(tabId);
  };

  const closeTab = (tabId: string) => {
    const tab = tabs.find((t) => t.id === tabId);
    if (tab) {
      tab.ws?.close();
      tab.terminal?.dispose();
    }

    setTabs((prev) => prev.filter((t) => t.id !== tabId));

    if (activeTabId === tabId) {
      const remainingTabs = tabs.filter((t) => t.id !== tabId);
      setActiveTabId(remainingTabs.length > 0 ? remainingTabs[remainingTabs.length - 1].id : null);
    }
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      tabs.forEach((tab) => {
        tab.ws?.close();
        tab.terminal?.dispose();
      });
    };
  }, []);

  const getSpanIcon = (spanType: string) => {
    switch (spanType?.toLowerCase()) {
      case "llm":
        return "🤖";
      case "tool":
        return "🔧";
      case "agent":
        return "🎯";
      case "chain":
        return "🔗";
      default:
        return "📍";
    }
  };

  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case "success":
        return "text-green-400";
      case "error":
        return "text-red-400";
      case "running":
        return "text-yellow-400";
      default:
        return "text-gray-400";
    }
  };

  return (
    <DashboardLayout>
      <div className="h-[calc(100vh-8rem)] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Terminal</h1>
            <p className="text-sm text-gray-500">
              Run commands, launch agents, and see traces in real-time
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowTracePanel(!showTracePanel)}
              className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                showTracePanel
                  ? "bg-primary-100 text-primary-700"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {traceConnected ? (
                <SignalIcon className="h-4 w-4 text-green-500" />
              ) : (
                <SignalSlashIcon className="h-4 w-4 text-red-500" />
              )}
              {showTracePanel ? "Hide" : "Show"} Traces
            </button>
            <button
              onClick={createNewTerminal}
              disabled={isConnecting || !isLoaded}
              className="inline-flex items-center gap-2 rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <PlusIcon className="h-5 w-5" />
              New Terminal
            </button>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
            {error}
          </div>
        )}

        {/* Main Content Area */}
        <div className="flex-1 flex gap-4 min-h-0">
          {/* Terminal Container */}
          <div
            className={`bg-[#1e1e2e] rounded-xl shadow-lg overflow-hidden flex flex-col ${
              showTracePanel ? "flex-1" : "w-full"
            }`}
          >
            {/* Tab Bar */}
            {tabs.length > 0 && (
              <div className="flex items-center bg-[#313244] px-2 py-1 gap-1 overflow-x-auto">
                {tabs.map((tab) => (
                  <div
                    key={tab.id}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm cursor-pointer transition-colors ${
                      activeTabId === tab.id
                        ? "bg-[#1e1e2e] text-[#cdd6f4]"
                        : "text-[#a6adc8] hover:bg-[#45475a]"
                    }`}
                    onClick={() => setActiveTabId(tab.id)}
                  >
                    <CommandLineIcon className="h-4 w-4" />
                    <span>{tab.name}</span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        closeTab(tab.id);
                      }}
                      className="ml-1 p-0.5 rounded hover:bg-[#585b70]"
                    >
                      <XMarkIcon className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
                <button
                  onClick={createNewTerminal}
                  disabled={isConnecting}
                  className="p-1.5 rounded-md text-[#a6adc8] hover:bg-[#45475a] transition-colors"
                >
                  <PlusIcon className="h-4 w-4" />
                </button>
              </div>
            )}

            {/* Terminal Area */}
            <div className="flex-1 p-2">
              {tabs.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-[#6c7086]">
                  <CommandLineIcon className="h-16 w-16 mb-4" />
                  <p className="text-lg mb-2">No terminals open</p>
                  <p className="text-sm mb-4">Click "New Terminal" to start a shell session</p>
                  <button
                    onClick={createNewTerminal}
                    disabled={isConnecting || !isLoaded}
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[#89b4fa] text-[#1e1e2e] font-medium hover:bg-[#b4befe] transition-colors disabled:opacity-50"
                  >
                    <PlusIcon className="h-5 w-5" />
                    {isConnecting ? "Connecting..." : "New Terminal"}
                  </button>
                </div>
              ) : (
                <div ref={terminalRef} className="h-full w-full" style={{ minHeight: "400px" }} />
              )}
            </div>
          </div>

          {/* Trace Panel */}
          {showTracePanel && (
            <div
              className="bg-white rounded-xl shadow-lg border border-gray-200 flex flex-col overflow-hidden"
              style={{ width: `${tracePanelWidth}px`, minWidth: "300px", maxWidth: "600px" }}
            >
              {/* Panel Header */}
              <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between bg-gray-50">
                <div className="flex items-center gap-2">
                  <h2 className="font-semibold text-gray-900">Live Traces</h2>
                  <span
                    className={`w-2 h-2 rounded-full ${
                      traceConnected ? "bg-green-500" : "bg-red-500"
                    }`}
                  />
                </div>
                <button
                  onClick={() => setActiveTraces(new Map())}
                  className="text-xs text-gray-500 hover:text-gray-700"
                >
                  Clear
                </button>
              </div>

              {/* Trace List */}
              <div className="flex-1 overflow-y-auto">
                {activeTraces.size === 0 ? (
                  <div className="p-8 text-center text-gray-500">
                    <SignalIcon className="h-12 w-12 mx-auto mb-3 text-gray-300" />
                    <p className="font-medium">Waiting for traces...</p>
                    <p className="text-sm mt-1">
                      Run a command with <code className="bg-gray-100 px-1 rounded">tm-trace</code>{" "}
                      to see live updates
                    </p>
                  </div>
                ) : (
                  <div className="divide-y divide-gray-100">
                    {Array.from(activeTraces.values())
                      .reverse()
                      .map((trace) => (
                        <div key={trace.id} className="p-3">
                          {/* Trace Header */}
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                              <span
                                className={`w-2 h-2 rounded-full ${
                                  trace.completed
                                    ? trace.success
                                      ? "bg-green-500"
                                      : "bg-red-500"
                                    : "bg-yellow-500 animate-pulse"
                                }`}
                              />
                              <span className="font-medium text-gray-900 text-sm">
                                {trace.agent_name}
                              </span>
                            </div>
                            <div className="flex items-center gap-2 text-xs text-gray-500">
                              {trace.duration_ms && (
                                <span>{(trace.duration_ms / 1000).toFixed(2)}s</span>
                              )}
                              <span className="font-mono">{trace.id.slice(0, 8)}</span>
                            </div>
                          </div>

                          {/* Spans */}
                          <div className="space-y-1 pl-4 border-l-2 border-gray-200">
                            {trace.spans.slice(-10).map((event) => (
                              <div
                                key={event.id}
                                className="flex items-start gap-2 text-xs"
                              >
                                <span>{getSpanIcon(event.data?.span_type || "")}</span>
                                <div className="flex-1 min-w-0">
                                  <span className="font-medium text-gray-700 truncate block">
                                    {event.data?.name}
                                  </span>
                                  {event.data?.attributes &&
                                    Object.keys(event.data.attributes).length > 0 && (
                                      <span className="text-gray-400 truncate block">
                                        {JSON.stringify(event.data.attributes).slice(0, 50)}
                                        {JSON.stringify(event.data.attributes).length > 50
                                          ? "..."
                                          : ""}
                                      </span>
                                    )}
                                </div>
                                <span className={getStatusColor(event.data?.status || "")}>
                                  {event.data?.status}
                                </span>
                              </div>
                            ))}
                            {trace.spans.length > 10 && (
                              <div className="text-xs text-gray-400 pl-6">
                                +{trace.spans.length - 10} more spans
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                  </div>
                )}
              </div>

              {/* Panel Footer */}
              <div className="px-4 py-2 border-t border-gray-200 bg-gray-50 text-xs text-gray-500">
                {activeTraces.size} active trace{activeTraces.size !== 1 ? "s" : ""} •{" "}
                {Array.from(activeTraces.values()).reduce((sum, t) => sum + t.spans.length, 0)}{" "}
                spans
              </div>
            </div>
          )}
        </div>

        {/* Help Text */}
        <div className="mt-4 text-sm text-gray-500">
          <p>
            <strong>Tip:</strong> Use{" "}
            <code className="px-1 py-0.5 bg-gray-100 rounded text-gray-700">
              tm-trace --agent &lt;agent-id&gt; &lt;command&gt;
            </code>{" "}
            to trace any command. Example:{" "}
            <code className="px-1 py-0.5 bg-gray-100 rounded text-gray-700">
              tm-trace --agent abc123 claude -p "Hello"
            </code>
          </p>
        </div>
      </div>
    </DashboardLayout>
  );
}
