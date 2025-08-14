# Building an AI Agent with Pydantic AI and Google Gemini

## Introduction

This tutorial will guide you through the process of building a sophisticated AI agent using Python, Pydantic AI, and Google's Gemini large language model. You will learn how to configure an agent, provide it with custom tools to perform specific tasks, and integrate Pydantic Logfire for powerful, out-of-the-box observability.

The final result will be a command-line application where you can have a conversation with an AI agent that can query and summarize information from a simulated data stream.

## Prerequisites

- Python 3.8+ installed.
- A Google AI Studio account and a Gemini API key.
- Basic understanding of Python, including dataclasses and type hints.
- The necessary Python libraries installed. You can install them using pip:
  ```bash
  pip install pydantic-ai pydantic-logfire
  ```

## Step-by-Step Guide

### Step 1: Defining Agent Dependencies

First, we need a way to manage and pass state to our agent's tools. Pydantic AI handles this through a dependencies class. In our case, the agent needs access to the state of the "Firehose" data stream.

We'll define a simple dataclass to hold this state. This class will be passed to our agent's tools at runtime.

```python
from dataclasses import dataclass
from firehose_state import FirehoseState # Placeholder for our data handling logic

@dataclass
class AgentDependencies:
    """Holds the state required by the agent's tools."""
    state: FirehoseState
```

### Step 2: Configuring the Pydantic AI Agent

Now, let's create the core of our application: the AI agent. We will instantiate the `pydantic_ai.Agent` class and configure it with the LLM we want to use, the dependencies it requires, the expected output format, and a system prompt.

- **LLM Model**: We specify `"google-gla:gemini-2.0-flash"` to use Google's fast and efficient Gemini model.
- **`deps_type`**: This points to our `AgentDependencies` class, telling the agent what kind of state to expect.
- **`output_type`**: For this example, we'll keep it simple and expect a plain string (`str`) as the final output. Pydantic AI also allows you to specify a Pydantic model for structured, validated output.
- **`system_prompt`**: This is a crucial set of instructions that tells the AI its purpose, what tools it has, and how it should behave. A detailed system prompt leads to more reliable and accurate agent performance.

```python
import pydantic_ai
from typing import List

# --- Agent Configuration ---
firehose_agent = pydantic_ai.Agent(
    "google-gla:gemini-2.0-flash",
    deps_type=AgentDependencies,
    output_type=str,
    system_prompt="""
You are a monitoring agent for the ATProto Firehose. You can answer questions about
the current state of the firehose data, filter messages by topic, and summarize what
people are saying about specific topics. You have two filtering options:

1. filter_threads_by_topic - returns complete conversation threads where any post mentions the topic
2. get_longest_threads - returns the threads with the most posts, useful for finding the most active discussions

When asked to analyze discussions or conversations about a topic, prefer filter_threads_by_topic
to get the full context of conversations. Use get_longest_threads to find the most active discussions.
Then provide thoughtful summaries of the main themes, sentiments, and key discussion points.

It may be interesting to quote snippets of the threads directly to give more depth to your summaries.

If the user asks for a complex set of topics, you may need to break it down into smaller parts and
process each one separately before combining the results.
""",
)
```

### Step 3: Creating a Tool for the Agent

Tools are standard Python functions that the agent can call to perform actions. By decorating a function with `@firehose_agent.tool`, we make it available to the AI, which can intelligently decide when to call it based on the user's query.

The first argument of any tool function must be a `RunContext`, which provides access to the dependencies we defined earlier.

```python
@firehose_agent.tool
def filter_threads_by_topic(
    ctx: pydantic_ai.RunContext[AgentDependencies],
    topic: str,
    limit: int = 10,
    preferred_langs: List[str] = None,
) -> List[str]:
    """
    Filter threads using advanced matching: semantic similarity, context awareness, language.
    This function would contain the logic to search the FirehoseState.
    """
    # In a real application, this would filter ctx.deps.state
    print(f"--- Tool called: Filtering for topic '{topic}' ---")
    # Placeholder implementation
    return [f"Thread about {topic} 1", f"Thread about {topic} 2"]
```

### Step 4: Running the Agent

With the agent configured and a tool defined, we can now process user queries. We call the agent's `run_sync()` method, passing the user's query and an instance of our `AgentDependencies` class.

This call triggers the full AI reasoning loop: the agent analyzes the query, decides if it needs to call a tool, executes the tool if necessary, and then formulates a final response.

```python
# Create an instance of our dependencies
deps = AgentDependencies(
    state=FirehoseState() # Initialize the state
)

# Keep track of the conversation
message_history = []

# Get user input
query = "What's happening on Blue Sky today?"

# Run the agent
response = firehose_agent.run_sync(
    query,
    deps=deps,
    message_history=message_history
)

print(response)
```

### Step 5: Adding Observability with Pydantic Logfire

Understanding what an AI agent is doing internally can be challenging. Pydantic Logfire simplifies this by providing detailed tracing with minimal setup.

By adding just two lines of code at the entry point of our application, we can automatically instrument our Pydantic AI agent.

```python
import logfire

if __name__ == "__main__":
    # Configure Logfire (disabling console output to keep our CLI clean)
    logfire.configure(console=False)

    # This single line instruments all Pydantic AI components
    logfire.instrument_pydantic_ai()

    # Call our main application logic
    main()
```

When you run your application, Logfire will capture the entire execution flow—from the initial query to the LLM's reasoning, tool calls, and final output—and send it to your Pydantic Logfire dashboard for easy visualization and debugging.

## Complete Code Example

Here is the complete, self-contained Python script for the AI agent.

```python
# main.py
import pydantic_ai
import logfire
from dataclasses import dataclass
from typing import List

# Note: The video tutorial does not provide the full implementation for FirehoseState.
# The class below is a placeholder to make the example runnable.
class FirehoseState:
    """A placeholder class to represent the state of the Blue Sky Firehose data."""
    def __init__(self):
        print("Initialized Firehose State.")

    def load_firehose_data(self, source: str):
        print(f"Loading firehose data from {source}...")
        # In a real app, this would load and process data.
        pass

# --- Step 1: Define Agent Dependencies ---
@dataclass
class AgentDependencies:
    """Holds the state required by the agent's tools."""
    state: FirehoseState

# --- Step 2: Configure the Pydantic AI Agent ---
firehose_agent = pydantic_ai.Agent(
    "google-gla:gemini-2.0-flash",
    deps_type=AgentDependencies,
    output_type=str,
    system_prompt="""
You are a monitoring agent for the ATProto Firehose. You can answer questions about
the current state of the firehose data, filter messages by topic, and summarize what
people are saying about specific topics. You have one primary tool:

1. filter_threads_by_topic - returns complete conversation threads where any post mentions the topic.

When asked to analyze discussions, use this tool to get the full context of conversations.
Then provide thoughtful summaries of the main themes, sentiments, and key discussion points.
""",
)

# --- Step 3: Create a Tool for the Agent ---
@firehose_agent.tool
def filter_threads_by_topic(
    ctx: pydantic_ai.RunContext[AgentDependencies],
    topic: str,
    limit: int = 10,
    preferred_langs: List[str] = None,
) -> List[str]:
    """
    Filter threads using advanced matching: semantic similarity, context awareness, language.
    This function would contain the logic to search the FirehoseState.
    """
    print(f"\n--- Tool Executed: Filtering for topic '{topic}' with limit {limit} ---\n")
    # In a real application, this would filter data from ctx.deps.state
    return [f"This is a sample thread about {topic}.", f"Another interesting post discusses {topic}."]

# --- Main Application Logic ---
def main():
    """Main function to run the CLI-based chat agent."""
    state = FirehoseState()
    state.load_firehose_data("firehose_capture.bin") # Simulate loading data

    deps = AgentDependencies(state=state)
    message_history = []

    print("\n--- ATProto Firehose Agent ---")
    print("Type your questions or 'quit' to exit.")
    print("-" * 40)

    while True:
        try:
            query = input("> ").strip()
            if query.lower() in ["quit", "exit", "q"]:
                print("Goodbye!")
                break
            if not query:
                continue

            response = firehose_agent.run_sync(
                query,
                deps=deps,
                message_history=message_history
            )

            print(f"\nAgent: {response.output}\n")
            message_history.extend(response.new_messages())

        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

# --- Step 5: Integrate Logfire and Run the App ---
if __name__ == "__main__":
    # Configure Logfire (set your API key via an environment variable)
    logfire.configure(console=False)

    # Automatically instrument Pydantic AI components
    logfire.instrument_pydantic_ai()

    # Run the main application
    main()
```

## Conclusion

You have successfully built an AI agent that leverages the power of Google Gemini and the structured framework of Pydantic AI. You've learned how to define custom tools to give your agent new capabilities and how to effortlessly add deep observability with Pydantic Logfire.

From here, you could explore several next steps:
- **Structured Output:** Modify the agent's `output_type` to a Pydantic model to receive structured JSON data instead of a simple string.
- **More Complex Tools:** Add more tools that can interact with databases, call external APIs, or perform other complex operations.
- **Web Deployment:** Wrap the agent in a web framework like FastAPI to make it accessible over the internet.
