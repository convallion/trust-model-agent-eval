"""
TrustModel Agent Instrumentation Example

This example shows how to instrument an AI agent to collect traces.
The SDK automatically patches common LLM libraries (Anthropic, OpenAI, LangChain).
"""

import asyncio
import os

# Set your API key
os.environ["TRUSTMODEL_API_KEY"] = "your-api-key-here"

from trustmodel import instrument
from trustmodel.connect import TracedAgent


# Method 1: One-line instrumentation with auto-patching
def simple_instrumentation():
    """Simple instrumentation - patches LLM libraries automatically."""
    handle = instrument(
        agent_name="my-coding-agent",
    )

    # Now all LLM calls are traced automatically
    # Example with Anthropic:
    try:
        import anthropic

        client = anthropic.Anthropic()
        message = client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=1024,
            messages=[{"role": "user", "content": "Hello!"}],
        )
        print(message.content[0].text)
    except ImportError:
        print("Anthropic not installed, skipping example")

    handle.shutdown()


# Method 2: Using TracedAgent base class
class MyAgent(TracedAgent):
    """Custom agent with manual tracing control."""

    async def run(self, task: str, **kwargs):
        """Execute the agent's main task."""
        # Trace a custom span
        with self.span("process_task"):
            # Record an LLM call manually
            self.record_llm_call(
                model="claude-3-opus",
                prompt=task,
                response="Task completed successfully",
                input_tokens=50,
                output_tokens=100,
            )

            # Trace a tool call
            with self.tool_span("code_search"):
                # Simulate tool execution
                result = {"files": ["main.py", "utils.py"]}
                return result


async def traced_agent_example():
    """Using the TracedAgent base class."""
    handle = instrument(agent_name="traced-agent-example")

    agent = MyAgent(name="my-agent", tracer=handle.tracer)

    # Run the agent
    result = await agent("Find relevant code files")
    print(f"Agent result: {result}")

    handle.shutdown()


# Method 3: Manual span creation
def manual_tracing():
    """Manual span creation for fine-grained control."""
    from trustmodel.connect import Tracer, get_tracer

    handle = instrument(agent_name="manual-trace-agent")
    tracer = handle.tracer

    # Start a new trace
    trace_id = tracer.start_trace(metadata={"task": "example"})

    # Create spans manually
    with tracer.span("outer_operation"):
        # Nested span
        with tracer.span("inner_operation"):
            # Do some work
            pass

        # LLM span
        with tracer.span("llm_call", span_type="llm_call") as span:
            span.set_attribute("model", "claude-3")
            span.set_attribute("prompt", "Hello world")

    # End the trace
    tracer.end_trace(trace_id)

    handle.shutdown()


if __name__ == "__main__":
    print("=== Simple Instrumentation ===")
    simple_instrumentation()

    print("\n=== TracedAgent Example ===")
    asyncio.run(traced_agent_example())

    print("\n=== Manual Tracing ===")
    manual_tracing()

    print("\nDone! Check the TrustModel playground to view traces.")
