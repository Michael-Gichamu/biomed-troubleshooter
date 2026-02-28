"""
Conversational LangGraph Studio Troubleshooting Agent

This module provides a conversational, human-in-the-loop troubleshooting agent
for LangGraph Studio. The agent guides engineers through diagnostic workflows
with LLM-powered conversation and tool-based measurements.

Workflow Phases:
- initial: Engineer provides equipment model + problem
- clarifying: Agent asks clarifying questions  
- measuring: Agent guides to test points, collects measurements
- diagnosing: Agent analyzes accumulated evidence
- complete: Final diagnosis and recommendations provided
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Literal, Sequence, Annotated
import uuid
import os

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode
from langchain_groq import ChatGroq
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.tools import BaseTool

from src.studio.tools import get_tools


# =============================================================================
# CONVERSATIONAL AGENT STATE
# =============================================================================

@dataclass
class ConversationalAgentState:
    """
    State for conversational LangGraph Studio troubleshooting agent.
    
    Uses add_messages reducer for automatic message history management.
    """
    
    # === MESSAGES (using add_messages for automatic persistence) ===
    messages: Annotated[list[BaseMessage], add_messages] = field(default_factory=list)
    
    # === SESSION METADATA ===
    equipment_model: str = ""
    equipment_serial: str = ""
    
    # === INITIAL PROBLEM ===
    initial_problem: str = ""
    confirmed_symptoms: list[str] = field(default_factory=list)
    
    # === CONVERSATION TRACKING ===
    last_agent_message: str = ""
    is_awaiting_measurement: bool = False
    
    # === MEASUREMENT COLLECTION ===
    collected_measurements: list[dict] = field(default_factory=list)
    test_points_measured: set[str] = field(default_factory=set)
    test_points_required: list[str] = field(default_factory=list)
    current_test_point: str = ""
    current_measurement_type: str = "voltage_dc"
    
    # === DIAGNOSIS STATE ===
    signal_states: dict = field(default_factory=dict)
    overall_status: str = "unknown"
    hypothesis: dict = field(default_factory=dict)
    diagnosis_confidence: float = 0.0
    
    # === EVIDENCE & RAG ===
    retrieved_evidence: list[dict] = field(default_factory=list)
    guidance_retrieved: list[str] = field(default_factory=list)
    
    # === OUTPUT ===
    recommendations: list[dict] = field(default_factory=list)
    response: dict = field(default_factory=dict)
    
    # === WORKFLOW CONTROL ===
    workflow_phase: Literal["initial", "clarifying", "measuring", "diagnosing", "complete", "error"] = "initial"
    
    # === ERROR HANDLING ===
    is_valid: bool = True
    validation_error: str = ""
    error_count: int = 0
    
    # === TIMING ===
    node_history: list[str] = field(default_factory=list)
    timestamp: str = ""


# =============================================================================
# AGENT NODE
# =============================================================================

SYSTEM_PROMPT = """You are a helpful electronics troubleshooting assistant.

When user says hi/hello, respond naturally like a person would.
When user describes a problem, immediately help them.

YOUR JOB:
1. Listen to what the engineer tells you
2. If they mention equipment, get the model if needed  
3. Query the diagnostic knowledge base for fault probabilities
4. Guide them through troubleshooting steps in order

TOOLS:
- query_diagnostic_knowledge: Get fault probabilities
- get_equipment_configuration: Find test points
- read_multimeter: Read multimeter
- enter_manual_reading: Manual entry if USB fails

WORKFLOW:
1. Get equipment model if not provided
2. Call get_equipment_configuration with request_type="faults" 
3. Execute recovery steps in order

Respond naturally.
"""


def get_system_prompt(state: ConversationalAgentState) -> str:
    """Generate the system prompt with current state."""
    return SYSTEM_PROMPT.format(
        equipment_model=state.equipment_model or "not specified",
        workflow_phase=state.workflow_phase,
        measurement_count=len(state.collected_measurements)
    )


def add_measurement(state: ConversationalAgentState, measurement: dict) -> dict:
    """Add a measurement to the collected measurements."""
    test_point = measurement.get("test_point", measurement.get("test_point_id", ""))
    
    # Determine signal state from threshold if equipment is known
    signal_state = "unknown"
    if state.equipment_model and test_point:
        try:
            from src.infrastructure.equipment_config import get_equipment_config
            config = get_equipment_config(state.equipment_model)
            signal_state = config.interpret_signal(test_point, measurement.get("value", 0))
        except Exception:
            pass
    
    measurement_with_state = {
        **measurement,
        "signal_state": signal_state,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    return {
        "collected_measurements": state.collected_measurements + [measurement_with_state],
        "test_points_measured": state.test_points_measured | {test_point},
        "signal_states": {**state.signal_states, test_point: signal_state}
    }


# =============================================================================
# AGENT NODE
# =============================================================================

def create_agent_node():
    """Create the agent node that runs the LLM with tools."""
    from langgraph.prebuilt import create_react_agent
    import os
    
    # Get tools
    tools = get_tools()
    
    # Get LLM configuration from environment
    provider = os.getenv("LLM_PROVIDER", "groq").lower()
    model = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
    
    llm = None
    
    if provider == "groq":
        from langchain_groq import ChatGroq
        api_key = os.getenv("GROQ_API_KEY", "")
        if api_key:
            llm = ChatGroq(
                model=model,
                groq_api_key=api_key,
                temperature=0.1
            )
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        api_key = os.getenv("OPENAI_API_KEY", "")
        if api_key:
            llm = ChatOpenAI(
                model=model,
                api_key=api_key,
                temperature=0.1
            )
    else:
        print(f"[WARN] Unknown LLM provider: {provider}, trying Groq")
        from langchain_groq import ChatGroq
        api_key = os.getenv("GROQ_API_KEY", "")
        if api_key:
            llm = ChatGroq(
                model=model,
                groq_api_key=api_key,
                temperature=0.1
            )
    
    # Fallback to direct Groq if needed
    if llm is None:
        import os
        provider = os.getenv("LLM_PROVIDER", "groq")
        model = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
        
        if provider == "groq":
            from langchain_groq import ChatGroq
            api_key = os.getenv("GROQ_API_KEY", "")
            if not api_key:
                raise RuntimeError("GROQ_API_KEY not set in environment")
            llm = ChatGroq(
                model=model,
                groq_api_key=api_key,
                temperature=0.1
            )
    
    if llm is None:
        raise RuntimeError(
            f"Failed to create LLM client. "
            f"Provider: {provider}, Model: {model}. "
            f"Please check your .env file - ensure LLM_PROVIDER and LLM_MODEL are set correctly, "
            f"and the corresponding API_KEY is provided."
        )
    
    # Create the ReAct agent
    agent = create_react_agent(llm, tools)
    
    return agent


def agent_node(state: ConversationalAgentState, config: "RunnableConfig" = None) -> dict:
    """Run the agent on the current messages.
    
    With add_messages, LangGraph automatically handles message history.
    We just need to return the result messages.
    """
    if config is None:
        config = {}
    
    # Get the agent
    agent = create_agent_node()
    
    # Add system message - this will be filtered out by add_messages
    from langchain_core.messages import SystemMessage
    system_msg = SystemMessage(content=get_system_prompt(state))
    
    # Build input: system message + current messages (LangGraph will merge with history)
    input_messages = [system_msg] + list(state.messages)
    
    # Run the agent
    result = agent.invoke(
        {"messages": input_messages},
        config
    )
    
    # Get the messages from result
    result_messages = result.get("messages", [])
    
    # Filter out system message from result
    ai_messages = []
    for msg in result_messages:
        msg_type = getattr(msg, 'type', str(msg))
        if msg_type not in ('system', 'SystemMessage'):
            ai_messages.append(msg)
    
    # Get last AI message for tracking
    last_message = ai_messages[-1] if ai_messages else None
    
    updates = {
        "messages": ai_messages,  # add_messages will merge this with history
        "last_agent_message": last_message.content if hasattr(last_message, "content") else str(last_message) if last_message else ""
    }
    
    # Check if measurement was collected via tool
    tool_measurements = []
    for msg in ai_messages:
        if hasattr(msg, "name") and msg.name in ("enter_manual_reading", "read_multimeter"):
            if hasattr(msg, "content"):
                try:
                    import json
                    tool_data = json.loads(msg.content)
                    if "test_point" in tool_data and "value" in tool_data:
                        tool_measurements.append(tool_data)
                except:
                    pass
    
    if tool_measurements:
        for meas in tool_measurements:
            updates.update(add_measurement(state, meas))
    
    return updates


# =============================================================================
# GRAPH CONSTRUCTION
# =============================================================================

def create_conversational_graph():
    """
    Create the conversational LangGraph for LangGraph Studio.
    
    Uses single-node architecture: agent_node handles everything.
    add_messages handles message history automatically.
    """
    from langgraph.graph import StateGraph, START, END
    from typing import Literal
    
    # Build the state graph
    builder = StateGraph(ConversationalAgentState)
    
    # Single node - the agent handles everything
    builder.add_node("agent", agent_node)
    
    # Add edges
    builder.add_edge(START, "agent")
    builder.add_edge("agent", END)
    
    # Compile with checkpointer for LangGraph Studio
    checkpointer = MemorySaver()
    graph = builder.compile(checkpointer=checkpointer)
    
    return graph


# =============================================================================
# GRAPH FACTORY FOR LANGGRAPH STUDIO
# =============================================================================

def graph():
    """
    Return the compiled conversational graph for LangGraph Studio.
    
    This is the factory function that LangGraph Studio calls.
    """
    return create_conversational_graph()


# =============================================================================
# TEST / ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    # Test the graph creation
    print("Creating conversational graph...")
    g = create_conversational_graph()
    print("Graph created successfully!")
    print(f"Graph nodes: {list(g.nodes.keys())}")
