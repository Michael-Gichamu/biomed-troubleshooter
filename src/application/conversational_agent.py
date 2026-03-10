"""
Diag - Conversational Troubleshooting Assistant
Refactored for improved UX, hardware polling, and interactive flow.
"""

import os
import re
import json
import uuid
from typing import Any, Optional, Annotated, Sequence
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool

from src.studio.tools import get_tools


# =============================================================================
# CONVERSATIONAL AGENT STATE
# =============================================================================

from typing import TypedDict

class ConversationalAgentState(TypedDict):
    """State for the Diag conversational agent."""
    messages: Annotated[list[BaseMessage], add_messages]
    equipment_model: str
    current_test_point: str
    is_session_complete: bool
    measurements: list
    current_step: int
    total_steps: int
    step_description: str
    awaiting_stabilization: bool
    last_poll_status: str
    next_node: str

# =============================================================================
# SYSTEM PROMPT
# =============================================================================

SYSTEM_PROMPT = """You are "Diag", a professional Biomedical Engineering Diagnostic Assistant. 

DIAGNOSTIC PRINCIPLES:
1. EQUIPMENT FIRST: Identify the equipment model first (e.g., "cctv-psu-24w-v1").
2. TALK-BEFORE-ACT: Always provide a brief conversational update BEFORE calling any tool. Explain what you are doing (e.g., "I will now get the guidance for TP1...").
3. VISUAL GUIDANCE: Use `get_test_point_guidance` to show the user where to probe. You MUST mention the image in your response for it to render (e.g., "Here is the guidance image:").
4. INTERACTIVE POLLING: Use `wait_for_multimeter_reading` to collect stable measurements.
5. ONE STEP AT A TIME: Guide the user through exactly one test point at a time.

INTERACTION STYLE:
- Be concise, technical, yet helpful.
- For images: MD images returned by tools will render automatically if you include them in your response or if they are part of the tool output history.
- Polling: Specifically tell the user: "I'm polling the meter now... please place your probes on [Test Point]."

HARDWARE ERROR HANDLING:
- If `wait_for_multimeter_reading` returns "timeout", explain this to the user.
- Offer them a choice: retry or enter the value manually using `enter_manual_reading`.

After a successful measurement, interpret it against thresholds and decide on the next step. If the fault is found, conclude with "SESSION COMPLETED".
"""

# =============================================================================
# NODES
# =============================================================================

def agent_node(state: ConversationalAgentState):
    """Reasoning node that generates prose and tool calls."""
    from src.infrastructure.llm_client import get_llm
    llm = get_llm()
    tools = get_tools()
    llm_with_tools = llm.bind_tools(tools)
    
    # Enrichment
    sys_content = SYSTEM_PROMPT
    if state.get("equipment_model"):
        sys_content += f"\n\nCURRENT EQUIPMENT: {state['equipment_model']}"
    
    # Progress info
    sys_content += f"\n\nDIAGNOSIS PROGRESS: Step {state.get('current_step', 1)}"
    
    messages = [SystemMessage(content=sys_content)] + state.get("messages", [])
    response = llm_with_tools.invoke(messages)
    
    # Check for session completion in text or tool calls
    is_complete = "SESSION COMPLETED" in str(response.content)
    
    # Multimodal image handling: Find the latest image data in history to re-attach if needed
    # (Actually, in this refactor, we rely on Markdown images from RAG tools mostly)
    
    return {
        "messages": [response],
        "is_session_complete": is_complete
    }

def tool_node(state: ConversationalAgentState):
    """Executes tool calls."""
    from langgraph.prebuilt import ToolNode
    node = ToolNode(get_tools())
    return node.invoke(state)

def analyze_and_route_node(state: ConversationalAgentState):
    """Analyzes the latest tool result and determines graph path."""
    messages = state.get("messages", [])
    if not messages:
        return {"next_node": "agent"}
        
    last_msg = messages[-1]
    if not isinstance(last_msg, ToolMessage):
        return {"next_node": "agent"}
    
    try:
        result = json.loads(last_msg.content)
        if isinstance(result, dict):
            status = result.get("status")
            
            # If polling success, go directly to analysis (agent)
            if status == "success":
                # Add to measurements
                measurements = state.get("measurements", [])
                new_measurement = {
                    "test_point": result.get("test_point_id"),
                    "value": result.get("value"),
                    "unit": result.get("unit"),
                    "timestamp": datetime.now().isoformat()
                }
                return {
                    "measurements": measurements + [new_measurement],
                    "next_node": "agent", # Succeed -> Agent analyzes
                    "current_step": state.get("current_step", 1) + 1
                }
            
            # If timeout, trigger interrupt
            if status == "timeout":
                return {
                    "next_node": "timeout_interrupt",
                    "last_poll_status": "timeout"
                }
    except:
        pass
        
    return {"next_node": "agent"}

def timeout_interrupt_node(state: ConversationalAgentState):
    """Pauses graph for user troubleshooting on hardware timeout."""
    test_point = state.get("current_test_point") or "the component"
    
    # Trigger graph interrupt
    answer = interrupt({
        "question": f"I couldn't detect a reading at {test_point}. Are the probes connected?",
        "options": ["retry", "manual entry", "cancel"],
        "test_point": test_point
    })
    
    # Resuming logic
    # If user wants to retry, we'll go back to agent/tools
    # If user wants manual, they can provide it next turn as a human message
    return {
        "messages": [HumanMessage(content=f"User selected: {answer}")],
        "last_poll_status": ""
    }

# =============================================================================
# GRAPH CONSTRUCTION
# =============================================================================

def should_continue_after_agent(state: ConversationalAgentState):
    messages = state.get("messages", [])
    if not messages:
        return END
        
    last_msg = messages[-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "tools"
    if state.get("is_session_complete"):
        return END
    return END

def route_after_tools(state: ConversationalAgentState):
    # This logic is handled by analyze_and_route_node now to be more explicit
    return "analyze"

def route_from_analysis(state: ConversationalAgentState):
    # Determine where to go based on analysis results stored in keys
    # Actually, we can use a simpler conditional edge
    pass

def create_diag_graph():
    builder = StateGraph(ConversationalAgentState)
    
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tool_node)
    builder.add_node("analyze", analyze_and_route_node)
    builder.add_node("timeout_interrupt", timeout_interrupt_node)
    
    builder.add_edge(START, "agent")
    
    builder.add_conditional_edges(
        "agent",
        should_continue_after_agent,
        {
            "tools": "tools",
            END: END
        }
    )
    
    builder.add_edge("tools", "analyze")
    
    builder.add_conditional_edges(
        "analyze",
        lambda x: x.get("next_node", "agent"),
        {
            "agent": "agent",
            "timeout_interrupt": "timeout_interrupt"
        }
    )
    
    builder.add_edge("timeout_interrupt", "agent")
    
    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)

def graph():
    """Factory for LangGraph Studio."""
    return create_diag_graph()
