"""TrustModel MCP Tracing Server.

Universal LLM tracing for any provider via MCP protocol.
Captures traces in LangSmith-compatible format.

Usage with Claude Desktop:
    Add to claude_desktop_config.json:
    {
        "mcpServers": {
            "trustmodel-tracing": {
                "command": "uvx",
                "args": ["trustmodel-mcp"]
            }
        }
    }
"""

__version__ = "0.1.0"
