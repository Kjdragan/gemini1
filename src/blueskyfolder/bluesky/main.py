"""CLI agent for ATProto Firehose using Pydantic AI + Gemini + Logfire."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import List

import logfire
import pydantic_ai
from dotenv import load_dotenv
load_dotenv()  # loads .env from the repo root when run from root



# --- Placeholder Firehose state -------------------------------------------------
class FirehoseState:
    """Placeholder representing the Blue Sky/ATProto Firehose state."""

    def __init__(self) -> None:
        print("Initialized Firehose State.")

    def load_firehose_data(self, source: str) -> None:
        print(f"Loading firehose data from {source}...")
        # In a real app, this would load and process data.
        return None


# --- Agent dependencies ---------------------------------------------------------
@dataclass
class AgentDependencies:
    """Holds state required by the agent's tools."""

    state: FirehoseState


# --- Agent configuration --------------------------------------------------------
firehose_agent = pydantic_ai.Agent(
    "google-gla:gemini-2.5-flash",
    deps_type=AgentDependencies,
    output_type=str,
    system_prompt=(
        """
You are a monitoring agent for the ATProto Firehose. You can answer questions about
 the current state of the firehose data, filter messages by topic, and summarize what
 people are saying about specific topics. You have one primary tool:

 1. filter_threads_by_topic - returns complete conversation threads where any post mentions the topic.

 When asked to analyze discussions, use this tool to get the full context of conversations.
 Then provide thoughtful summaries of the main themes, sentiments, and key discussion points.
        """
    ),
)


# --- Tools ---------------------------------------------------------------------
@firehose_agent.tool
def filter_threads_by_topic(
    ctx: pydantic_ai.RunContext[AgentDependencies],
    topic: str,
    limit: int = 10,
    preferred_langs: List[str] | None = None,
) -> List[str]:
    """Return sample threads about the given topic.

    In a real application, this would query/filter data in ``ctx.deps.state``.
    """
    print(f"\n--- Tool Executed: Filtering for topic '{topic}' with limit {limit} ---\n")
    return [
        f"This is a sample thread about {topic}.",
        f"Another interesting post discusses {topic}.",
    ]


# --- CLI entrypoint -------------------------------------------------------------

def main() -> None:
    """Run the CLI chat agent."""
    # Load environment variables from .env if present (e.g., GOOGLE_API_KEY)


    # Configure Logfire and instrument Pydantic AI
    # Note: set LOGFIRE_API_KEY in env to send traces; otherwise local-only.
    logfire.configure(console=False)
    logfire.instrument_pydantic_ai()

    # Initialize state/dependencies
    state = FirehoseState()
    state.load_firehose_data("firehose_capture.bin")
    deps = AgentDependencies(state=state)

    message_history: list = []

    print("\n--- ATProto Firehose Agent ---")
    print("Type your questions or 'quit' to exit.")
    print("-" * 40)

    while True:
        try:
            query = input("> ").strip()
            if query.lower() in {"quit", "exit", "q"}:
                print("Goodbye!")
                break
            if not query:
                continue

            result = firehose_agent.run_sync(
                query,
                deps=deps,
                message_history=message_history,
            )

            # pydantic-ai returns an object with .output and .new_messages()
            print(f"\nAgent: {result.output}\n")
            message_history.extend(result.new_messages())

        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break
        except Exception as e:  # keep CLI resilient
            print(f"Error: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
