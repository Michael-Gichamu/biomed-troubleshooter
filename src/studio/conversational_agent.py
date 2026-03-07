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
from typing import Any, Optional, Literal, Sequence, Annotated
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

from langgraph.types import interrupt
from langchain_core.messages import SystemMessage, ToolMessage
import json

# =============================================================================
# CONVERSATIONAL AGENT STATE
# =============================================================================

@dataclass
class ConversationalAgentState:
    """
    State for conversational LangGraph Studio troubleshooting agent.
    """
    messages: Annotated[list[BaseMessage], add_messages] = field(default_factory=list)
    equipment_model: str = ""
    current_test_point: str = ""
    is_awaiting_human: bool = False
    is_session_complete: bool = False
    last_tool_result: dict = field(default_factory=dict)

# =============================================================================
# HELPER: IMAGE EMBEDDING
# =============================================================================

def format_message_content(text: str, image_data: Optional[dict] = None) -> Any:
    """
    Format message content as a list of blocks for LangGraph Studio rendering.
    """
    if not image_data:
        return text
        
    return [
        {"type": "text", "text": text},
        {
            "type": "image_url", 
            "image_url": {
                "url": f"data:{image_data.get('mime_type', 'image/jpeg')};base64,{image_data.get('image_base64')}"
            }
        }
    ]

# =============================================================================
# NODES
# =============================================================================

# =============================================================================
# HELPER: TOKEN MANAGEMENT
# =============================================================================

import re

def clean_messages_for_llm(messages: list[BaseMessage]) -> list[BaseMessage]:
    """
    Strip large base64 data URIs from message history to prevent token limits
    and state bloat in LangGraph Studio.
    """
    cleaned = []
    # Regex to find markdown image tags with base64 data
    base64_re = re.compile(r'!\[.*?\]\(data:.*?;base64,.*?\)')
    
    for msg in messages:
        # Clone the message to avoid side effects on the original UI representation
        new_msg = msg.copy()
        if hasattr(new_msg, "content") and isinstance(new_msg.content, str):
            new_msg.content = base64_re.sub("[IMAGE DATA STRIPPED FOR STABILITY]", new_msg.content)
            
            # Also check ToolMessage content which might be JSON containing base64
            if isinstance(new_msg, ToolMessage):
                try:
                    data = json.loads(new_msg.content)
                    if isinstance(data, dict) and "image_base64" in data:
                        data["image_base64"] = "[SENSITIVE DATA STRIPPED]"
                        new_msg.content = json.dumps(data)
                except:
                    pass
        cleaned.append(new_msg)
    return cleaned

# =============================================================================
# SYSTEM PROMPT
# =============================================================================

SYSTEM_PROMPT = """You are a professional Biomedical Engineering Diagnostic Assistant. 

DIAGNOSTIC PRINCIPLES:
1. DOCUMENT-FIRST: Before suggesting any tests, you MUST consult the equipment configuration and diagnostic knowledge base to identify the most probable faults.
2. ONE STEP AT A TIME: Never provide multiple instructions or measurements in one message. Guide the user through EXACTLY ONE test point, get the result, and then evaluate.
3. PROACTIVE AUTO-COLLECTION: When you guide a user to a test point, you MUST call the `read_multimeter` tool in the same message turn. NEVER provide guidance without a tool call.
4. SESSION CONTINUITY: After every tool result, analyze it against thresholds. If an anomaly is found, immediately move to the next logical step in the fault signature sequence. DO NOT stop the diagnostic session until a final "SESSION COMPLETED" status is reached.

INTERACTION STYLE:
- Be concise and technical.
- Locating the point: Provide the physical description and image.
- MUST provide text instructions: Always explain what the user should do in your response content.
- Polling Feedback: Explicitly state "Polling the meter now... please place your probes on [Test Point]." This text must be in the final message content.
- Interpreting: After a tool returns a value, analyze it against the expected range in the docs before moving to the next point.

WORKFLOW:
1. Identify equipment model.
2. Call `query_diagnostic_knowledge` and `get_equipment_configuration` (request_type='faults').
3. Based on probabilities, choose the HIGHEST priority fault and its signatures.
4. For each signature:
   a. Call `get_test_point_guidance`.
   b. Provide guidance + "Polling..." message.
   c. Call `read_multimeter` immediately in the same turn.
   d. Analyze result. If missing/degraded, continue to next signature or diagnose.
5. When diagnosis is clear, provide final repair instructions and state "SESSION COMPLETED".
"""


def agent_node(state: ConversationalAgentState):
    """The planning/reasoning node."""
    from src.infrastructure.llm_client import get_llm
    llm = get_llm()
    tools = get_tools()
    llm_with_tools = llm.bind_tools(tools)
    
    # Clean history to keep token count low and prevent UI hangs
    cleaned_messages = clean_messages_for_llm(state.messages)
    
    # System prompt
    sys_msg = SystemMessage(content=SYSTEM_PROMPT)
    
    # Run LLM
    response = llm_with_tools.invoke([sys_msg] + cleaned_messages)
    
    # IMAGE ENRICHMENT: Find the most recent test point guidance in history
    # and attach it to the CURRENT response content if applicable.
    # This ensures images show up even while the multimeter is polling.
    image_data = None
    for m in reversed(state.messages):
        if isinstance(m, ToolMessage):
            try:
                res_data = json.loads(m.content)
                if isinstance(res_data, dict) and res_data.get("image_base64"):
                    image_data = res_data
                    break
            except:
                continue
    
    # Format as multimodal content blocks if image exists
    response.content = format_message_content(response.content, image_data)
    
    # Session completion check
    is_complete = False
    if isinstance(response.content, str):
        if "SESSION COMPLETED" in response.content:
            is_complete = True
    elif isinstance(response.content, list):
        for block in response.content:
            if block.get("type") == "text" and "SESSION COMPLETED" in block.get("text", ""):
                is_complete = True
                break
                
    return {"messages": [response], "is_session_complete": is_complete}

def tool_node(state: ConversationalAgentState):
    """Standard tool execution node with a twist for images."""
    last_msg = state.messages[-1]
    if not hasattr(last_msg, "tool_calls") or not last_msg.tool_calls:
        return {}
        
    tools_map = {t.name: t for t in get_tools()}
    results = []
    
    for tool_call in last_msg.tool_calls:
        tool = tools_map.get(tool_call["name"])
        if tool:
            print(f"[TOOL] Running {tool_call['name']}...")
            result = tool.invoke(tool_call["args"])
            
            # Special handling for guidance images
            # To prevent state bloat, we strip the image_base64 immediately 
            # after it's produced to keep the persistent state lightweight.
            if tool_call["name"] == "get_test_point_guidance" and isinstance(result, dict):
                # Keep the image data for the NEXT node to use (it's in the ToolMessage content)
                # But we can strip it here and the agent_node will have to get it 
                # FROM the tool result if we want to show it in the UI.
                # Actually, the most robust way is to strip it AFTER the next agent step.
                pass
                
            results.append(ToolMessage(
                tool_call_id=tool_call["id"],
                content=json.dumps(result) if isinstance(result, dict) else str(result)
            ))
            
    return {"messages": results}

# =============================================================================
# ROUTING
# =============================================================================

def should_continue(state: ConversationalAgentState):
    """Route after agent node."""
    if state.is_session_complete:
        return END

    last_msg = state.messages[-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "tools"
        
    return END

def post_tool_route(state: ConversationalAgentState):
    """Route after tools node."""
    return "agent"

# =============================================================================
# GRAPH CONSTRUCTION
# =============================================================================

def create_conversational_graph():
    """Build the custom interactive graph."""
    builder = StateGraph(ConversationalAgentState)
    
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tool_node)
    
    builder.add_edge(START, "agent")
    
    builder.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            END: END
        }
    )
    
    builder.add_edge("tools", "agent")
    
    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)

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
    print("Creating interactive graph...")
    g = create_conversational_graph()
    print("Success!")
