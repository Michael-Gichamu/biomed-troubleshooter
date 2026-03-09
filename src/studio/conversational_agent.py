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
    iteration_count: int = 0  # Track iterations to prevent infinite loops
    measurements: list = field(default_factory=list)  # Track all measurements taken

# =============================================================================
# HELPER: IMAGE EMBEDDING
# =============================================================================

def format_message_content(text: str, image_data: Optional[dict] = None) -> Any:
    """
    Format message content with the image PROMINENTLY as the first block.
    """
    if not image_data:
        return text
        
    return [
        {
            "type": "image_url", 
            "image_url": {
                "url": f"data:{image_data.get('mime_type', 'image/jpeg')};base64,{image_data.get('image_base64')}"
            }
        },
        {"type": "text", "text": text}
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
        
        if isinstance(new_msg.content, str):
            new_msg.content = base64_re.sub("[IMAGE DATA STRIPPED FOR STABILITY]", new_msg.content)
        elif isinstance(new_msg.content, list):
            # Clean multimodal content blocks
            new_content = []
            for block in new_msg.content:
                if isinstance(block, dict) and block.get("type") == "image_url":
                    new_content.append({"type": "text", "text": "[IMAGE ATTACHMENT STRIPPED FROM CONTEXT]"})
                else:
                    new_content.append(block)
            new_msg.content = new_content
            
        # Also check ToolMessage content which might be JSON containing base64
        if isinstance(new_msg, ToolMessage):
            try:
                data = json.loads(new_msg.content)
                if isinstance(data, dict):
                    if "image_base64" in data:
                        data["image_base64"] = "[SENSITIVE DATA STRIPPED]"
                    if "images" in data:
                        for img in data["images"]:
                            if isinstance(img, dict) and "image_base64" in img:
                                img["image_base64"] = "[SENSITIVE DATA STRIPPED]"
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
1. EQUIPMENT FIRST: You MUST identify the equipment model before providing any diagnostic guidance. If the `equipment_model` is not provided in your state, your ONLY goal is to ask the user for the model identifier (e.g., "cctv-psu-24w-v1"). NEVER assume a model.
2. DOCUMENT-FIRST: Once a model is identified, you MUST consult the equipment configuration and diagnostic knowledge base to identify probable faults before suggesting tests.
3. ONE STEP AT A TIME: Never provide multiple instructions or measurements in one message. Guide the user through EXACTLY ONE test point, get the result, and then evaluate.
4. PROACTIVE AUTO-COLLECTION: When you guide a user to a test point, you MUST call the `read_multimeter` tool in the same message turn. NEVER provide guidance without a tool call.
5. SMART TERMINATION - CRITICAL: After each measurement, analyze against expected thresholds. If a reading is OUT OF RANGE or indicates a fault, IMMEDIATELY conclude with diagnosis and recommendations. DO NOT continue to additional test points if you've already identified the fault. State "SESSION COMPLETED" when done.
6. ITERATION LIMIT: The session will auto-terminate after 10 measurement iterations. Provide your best diagnosis with available data if you reach this limit.

INTERACTION STYLE:
- Be concise and technical.
- Locating the point: ALWAYS provide visual guidance.
- Text instructions: Explain what the user should do.
- Polling Feedback: Explicitly state "Polling the meter now... please place your probes on [Test Point]."
- IMAGE PROVIDER: You ARE capable of showing images. When the user asks for one, or when you are guiding them to a test point, ALWAYS call a tool that provides image data (e.g., `get_equipment_configuration` with `request_type="all"` or `get_test_point_guidance`). 
- RENDER POLICY: The system will automatically attach and render the image from the latest tool output as the primary visual block. Do NOT include markdown links or base64 text in your response; just say "Here is the layout view..." or similar.
"""

# Maximum iterations to prevent infinite loops
MAX_ITERATIONS = 10


def agent_node(state: ConversationalAgentState):
    """The planning/reasoning node."""
    from src.infrastructure.llm_client import get_llm
    llm = get_llm()
    tools = get_tools()
    llm_with_tools = llm.bind_tools(tools)
    
    # Clean history to keep token count low
    cleaned_messages = clean_messages_for_llm(state.messages)
    
    # Detect equipment model from history if not in state
    equipment_model = state.equipment_model
    if not equipment_model:
        for m in reversed(state.messages):
            if isinstance(m, (HumanMessage, AIMessage, ToolMessage)):
                content = m.content if isinstance(m.content, str) else str(m.content)
                # Simple regex for model pattern or look for tool calls
                match = re.search(r"cctv-psu-[a-z0-9-]+", content.lower())
                if match:
                    equipment_model = match.group(0)
                    break
    
    # System prompt enrichment with state
    sys_content = SYSTEM_PROMPT
    if equipment_model:
        sys_content += f"\n\nCURRENT EQUIPMENT: {equipment_model}"
    
    sys_msg = SystemMessage(content=sys_content)
    
    # Run LLM
    response = llm_with_tools.invoke([sys_msg] + cleaned_messages)
    
    # Image Enrichment: Find latest guidance image or reference image
    image_data = None
    # We look through history to find the most recent ToolMessage that contains image data.
    # We search the ORIGINAL state.messages which have the base64 data.
    # We increase search depth to ensure images from early steps are still available.
    for m in reversed(state.messages):
        if isinstance(m, ToolMessage):
            try:
                res_data = json.loads(m.content)
                if isinstance(res_data, dict):
                    # Priority 1: Direct test point image
                    if res_data.get("image_base64"):
                        image_data = res_data
                        break
                    # Priority 2: Visual guide annotations from test point guidance
                    elif res_data.get("visual_guide") and isinstance(res_data["visual_guide"], list) and res_data["visual_guide"]:
                        # Fallback if image_base64 is present
                        if res_data.get("image_base64"):
                            image_data = res_data
                            break
                    # Priority 3: Bulk image list
                    elif "images" in res_data and res_data["images"]:
                        overview = next((img for img in res_data["images"] if "overview" in str(img.get("description", "")).lower() or "overview" in str(img.get("filename", "")).lower()), None)
                        image_data = overview or res_data["images"][0]
                        break
            except:
                continue
    
    # Format content blocks. Place image FIRST for maximum prominence.
    response.content = format_message_content(response.content, image_data)
    
    # Session completion check
    is_complete = False
    content_str = str(response.content)
    if "SESSION COMPLETED" in content_str:
        is_complete = True
                
    return {
        "messages": [response], 
        "is_session_complete": is_complete,
        "equipment_model": equipment_model,
        "iteration_count": state.iteration_count + 1
    }

def tool_node(state: ConversationalAgentState):
    """Standard tool execution node with a twist for images."""
    last_msg = state.messages[-1]
    if not hasattr(last_msg, "tool_calls") or not last_msg.tool_calls:
        return {}
        
    tools_map = {t.name: t for t in get_tools()}
    results = []
    measurements = []
    
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
            
            # Track measurements for diagnostic analysis
            if tool_call["name"] in ("read_multimeter", "enter_manual_reading") and isinstance(result, dict):
                if "value" in result and "test_point" in result:
                    measurement = {
                        "test_point": result.get("test_point"),
                        "value": result.get("value"),
                        "unit": result.get("unit", "V"),
                        "measurement_type": result.get("measurement_type", "unknown"),
                        "is_stable": result.get("is_stable", True)
                    }
                    measurements.append(measurement)
    
    return {
        "messages": results,
        "measurements": state.measurements + measurements
    }

# =============================================================================
# ROUTING
# =============================================================================

def should_continue(state: ConversationalAgentState):
    """Route after agent node - checks for session completion or max iterations."""
    # Check if session is complete
    if state.is_session_complete:
        return END
    
    # Check if we've exceeded max iterations - force diagnose
    if state.iteration_count >= MAX_ITERATIONS:
        return "diagnose"
    
    last_msg = state.messages[-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "tools"
        
    return END

def post_tool_route(state: ConversationalAgentState):
    """Route after tools node."""
    return "agent"

# =============================================================================
# DIAGNOSE NODE - Provides diagnosis when max iterations reached
# =============================================================================

def diagnose_node(state: ConversationalAgentState):
    """
    Diagnose node that provides final analysis when max iterations reached.
    This node analyzes accumulated measurements and provides a conclusion.
    """
    from src.infrastructure.llm_client import get_llm
    from langchain_core.messages import SystemMessage
    
    llm = get_llm()
    
    # Build measurement summary for diagnosis
    measurement_summary = ""
    if state.measurements:
        measurement_summary = "\n".join([
            f"- {m.get('test_point')}: {m.get('value')} {m.get('unit')} ({m.get('measurement_type')})"
            for m in state.measurements
        ])
    else:
        measurement_summary = "No measurements recorded."
    
    # Create diagnosis prompt
    diagnose_prompt = f"""You have reached the maximum number of diagnostic iterations (10). 

Based on the accumulated evidence, provide a final diagnosis:

MEASUREMENTS COLLECTED:
{measurement_summary}

Please provide:
1. Your best assessment of the fault
2. Recommended next steps or actions
3. Any additional tests that might help (if applicable)

End your response with "SESSION COMPLETED" to close this session.
"""
    
    response = llm.invoke([SystemMessage(content=diagnose_prompt)])
    
    # Add measurement summary as context
    response.content = f"[Diagnostic Summary - {len(state.measurements)} measurements taken]\n\n" + str(response.content)
    
    return {
        "messages": [response],
        "is_session_complete": True
    }


# =============================================================================
# GRAPH CONSTRUCTION
# =============================================================================

def create_conversational_graph():
    """Build the custom interactive graph."""
    builder = StateGraph(ConversationalAgentState)
    
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tool_node)
    builder.add_node("diagnose", diagnose_node)
    
    builder.add_edge(START, "agent")
    
    builder.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "diagnose": "diagnose",
            END: END
        }
    )
    
    builder.add_edge("tools", "agent")
    builder.add_edge("diagnose", END)
    
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
