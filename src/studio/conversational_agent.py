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
    Includes step tracking for human-in-the-loop diagnostic workflow.
    """
    messages: Annotated[list[BaseMessage], add_messages] = field(default_factory=list)
    equipment_model: str = ""
    current_test_point: str = ""
    is_awaiting_human: bool = False
    is_session_complete: bool = False
    is_paused_for_human: bool = False  # Flag to indicate we're waiting for user confirmation
    last_tool_result: dict = field(default_factory=dict)
    iteration_count: int = 0  # Track iterations to prevent infinite loops
    measurements: list = field(default_factory=list)  # Track all measurements taken
    
    # Step tracking for human-in-the-loop
    current_step: int = 1  # Current step number (1-indexed)
    total_steps: int = 5  # Total steps planned for diagnosis
    step_description: str = ""  # Description of current step
    pending_instruction: str = ""  # Instruction to show user after resume
    
    # Auto-measurement tracking - forces read_multimeter after guidance
    awaiting_test_point_guidance: bool = False  # Set to True after showing guidance
    last_guidance_test_point: str = ""  # The test point we just showed guidance for

# =============================================================================
# HELPER: IMAGE EMBEDDING
# =============================================================================

def format_message_content(text: str, image_data: Optional[dict] = None) -> str:
    """
    Format message content with inline markdown image rendering.
    
    Returns a markdown string with inline image:
    - Image: ![Test Point](image_url)
    - Text: follows after
    
    Or returns the original text string if no image_data is provided.
    """
    if not image_data:
        return text
    
    # Extract image URL
    image_url = image_data.get('image_url')
    
    if not image_url:
        return text
    
    # Build markdown content with image inline
    test_point_info = image_data.get('test_point', '')
    location_desc = image_data.get('location_description', '')
    
    # Use markdown format for inline image rendering
    # Use test point info as alt text for the image
    alt_text = test_point_info if test_point_info else "Test Point"
    markdown_image = f"![{alt_text}]({image_url})"
    
    # Add text content - include location info as header
    header = ""
    if test_point_info:
        header = f"### {test_point_info}"
        if location_desc:
            header += f" - {location_desc}"
        header += "\n\n"
    
    # Combine markdown image with text content
    markdown_content = f"{markdown_image}\n\n{header}{text}"
    
    return markdown_content

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
                    # No longer stripping base64 - we now use URL-based images
                    new_msg.content = json.dumps(data)
            except:
                pass
        cleaned.append(new_msg)
    return cleaned

# =============================================================================
# SYSTEM PROMPT
# =============================================================================

SYSTEM_PROMPT = """You are a professional Biomedical Engineering Diagnostic Assistant. 

# TOOLS AVAILABLE - YOU MUST USE THESE TOOLS

You have access to the following tools. When you need information, you MUST call these tools - do NOT guess or hallucinate:

1. **query_diagnostic_knowledge** - Query the diagnostic knowledge base for troubleshooting guidance. Use when you need diagnostic procedures or fault analysis.
   - Args: query, equipment_model, category (optional), top_k (optional)

2. **get_equipment_configuration** - Get equipment details including model info, test points, and expected values.
   - Args: equipment_model, request_type (optional: "all", "test_points", "model_info")
   - MUST call this first to get valid test points for the equipment

3. **get_test_point_guidance** - Get detailed guidance for measuring a specific test point (location, image, pro tips).
   - Args: equipment_model, test_point_id
   - MUST call this before measuring to show user where to place probes

4. **read_multimeter** - Automatically collect measurement readings from USB multimeter.
   - Args: equipment_model, test_point_id
   - Call this AFTER get_test_point_guidance to collect the actual measurement

5. **enter_manual_reading** - Allow user to manually enter a reading if multimeter is unavailable.
   - Args: equipment_model, test_point_id, reading_value, mode (optional)

**CRITICAL TOOL USAGE RULES:**
- When the user provides an equipment model → MUST call `get_equipment_configuration` to get valid test points
- Before any measurement → MUST call `get_test_point_guidance` first to show probe location
- After showing guidance → MUST call `read_multimeter` to collect the measurement
- Never ask user to manually report values → Always use `read_multimeter` or `enter_manual_reading`

STRICT DIAGNOSTIC BEHAVIOR RULES:

1. **NEVER HALLUCINATE** - Only use values from tool output. Never assume or guess measurement values.

2. **NEVER GUESS TEST POINTS** - Only use valid test points from equipment configuration. Call `get_equipment_configuration` or `get_test_point_guidance` to get the valid list.

3. **VALIDATE TOOL RESULTS** - If tool result contains guidance.error or invalid test point, discard it and choose a valid one from config.

4. **MANDATORY PAUSE AFTER EVERY MEASUREMENT** - After getting ANY measurement result, you MUST:
   - STOP your response
   - Say EXACTLY: "Press NEXT to continue diagnosis"
   - Do NOT continue automatically - wait for user confirmation

5. **DISPLAY IMAGES INLINE** - Use markdown format: `![Test Point](image_url)`

6. **RESPONSE FORMAT** - After each measurement, follow this structure:
   - WHY: Explain why this test point was selected
   - MEASUREMENT RESULT: Show the value clearly (e.g., "Voltage: 24.2V DC")
   - INTERPRETATION: Explain what the reading means (normal/abnormal/fault indicator)
   - NEXT ACTION: What you plan to do next
   - PAUSE: "Press NEXT to continue diagnosis"

DIAGNOSTIC PRINCIPLES:
1. EQUIPMENT FIRST: You MUST identify the equipment model before providing any diagnostic guidance. If the `equipment_model` is not provided in your state, your ONLY goal is to ask the user for the model identifier (e.g., "cctv-psu-24w-v1"). NEVER assume a model.
2. DOCUMENT-FIRST: Once a model is identified, you MUST consult the equipment configuration and diagnostic knowledge base to identify probable faults before suggesting tests.

**MEASUREMENT FLOW WITH MANDATORY PAUSE:**

1. When you need to measure a test point, call `read_multimeter` - it will:
   - FIRST: Show the test point guidance (image, location, pro tips)
   - THEN: Automatically start sampling and wait for stabilization
   - FINALLY: Return the stable reading

2. After showing guidance, tell the user to place probes and HOLD STEADY while sampling occurs:
   - GOOD: "Place the probes on the marked test point and hold them steady while I sample for a few seconds."

3. After getting the measurement result, you MUST pause:
   - Present the result using the response format (WHY, MEASUREMENT RESULT, INTERPRETATION, NEXT ACTION)
   - End with "Press NEXT to continue diagnosis"
   - DO NOT proceed to next step without user confirmation

**STEP TRACKING:**
- Always show current step like "Step X of Y: [Description]"
- Update current_step and total_steps as you progress

**INTERPRETATION:**
- After each measurement, interpret the result against RAG thresholds
- If a reading is OUT OF RANGE or indicates a fault, IMMEDIATELY conclude with diagnosis
- DO NOT continue to additional test points if you've already identified the fault

**TIMEOUT HANDLING:**
If `read_multimeter` returns status "timeout" or "timeout_unstable":
- Explain what happened and offer guidance
- Say "Press NEXT to continue diagnosis" to wait for user to retry

**ITERATION LIMIT:**
- The session will auto-terminate after 10 measurement iterations
- Provide your best diagnosis with available data if you reach this limit

**TALK-BEFORE-ACT - CRITICAL FOR UX:**
Before calling ANY tool, ALWAYS provide a brief conversational update to the user. This ensures the user sees text in the LangGraph Studio UI even when "Show Tool Calls" is toggled off.

IMAGE RENDERING:
- You ARE capable of showing images. When the user asks for one, or when you are guiding them to a test point, ALWAYS call a tool that provides image data (e.g., `get_equipment_configuration` with `request_type="all"` or `get_test_point_guidance`). 
- Images are shown inline using markdown format: ![Test Point](image_url). Do NOT include base64 text in your response.

STATE TRACKING:
- current_step: Tracks which diagnostic step you're on (1, 2, 3, etc.)
- total_steps: Total planned steps for this diagnosis
- Update these values as you progress through the diagnosis.
"""

# Maximum iterations to prevent infinite loops
MAX_ITERATIONS = 10


def agent_node(state: ConversationalAgentState):
    """The planning/reasoning node."""
    from src.infrastructure.llm_manager import invoke_with_tools_and_retry
    tools = get_tools()
    
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
    
    # Add step tracking info to system prompt
    sys_content += f"\n\nDIAGNOSIS PROGRESS: Step {state.current_step} of {state.total_steps}"
    if state.step_description:
        sys_content += f" - {state.step_description}"
    
    # CRITICAL: After EVERY measurement, the agent MUST include "Press NEXT to continue diagnosis"
    # The system will automatically pause after tools run, but the agent response should also
    # clearly indicate waiting for user confirmation.
    sys_content += """
    
    **MANDATORY RESPONSE FORMAT AFTER MEASUREMENTS:**
    After getting any measurement result, your response MUST end with:
    "Press NEXT to continue diagnosis"
    
    Do NOT continue automatically - wait for the user to confirm before proceeding.
    """
    
    sys_msg = SystemMessage(content=sys_content)
    
    # Run LLM with retry logic (handles RateLimitError, APIError, etc. with key/model rotation)
    response = invoke_with_tools_and_retry([sys_msg] + cleaned_messages, tools)
    
    # Image Enrichment: Find latest guidance image or reference image
    image_data = None
    # We look through history to find the most recent ToolMessage that contains image URL.
    # We search the ORIGINAL state.messages which have the URL-based image data.
    # We increase search depth to ensure images from early steps are still available.
    for m in reversed(state.messages):
        if isinstance(m, ToolMessage):
            try:
                res_data = json.loads(m.content)
                if isinstance(res_data, dict):
                    # Priority 1: Direct test point image (URL-based now)
                    if res_data.get("image_url"):
                        image_data = res_data
                        break
                    # Priority 2: Visual guide annotations from test point guidance
                    elif res_data.get("visual_guide") and isinstance(res_data["visual_guide"], list) and res_data["visual_guide"]:
                        # Fallback if image_url is present
                        if res_data.get("image_url"):
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
        "iteration_count": state.iteration_count + 1,
        "is_paused_for_human": False,  # Pause is handled in post_tool_route after tools run
        "current_step": state.current_step,
        "total_steps": state.total_steps,
        "awaiting_test_point_guidance": False,  # No longer needed - we pause after every measurement
        "last_guidance_test_point": state.last_guidance_test_point
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
    
    # Note: We no longer track awaiting_test_point_guidance - pause is now mandatory after every measurement
    return {
        "messages": results,
        "measurements": state.measurements + measurements
    }

# =============================================================================
# HUMAN-IN-THE-LOOP NODES
# =============================================================================

def wait_for_human(state: ConversationalAgentState):
    """
    Wait for human confirmation before continuing.
    This node uses interrupt() to pause the graph and wait for user input.
    
    STRICT DIAGNOSTIC RULE: After EVERY measurement, we MUST pause and wait for user to press NEXT.
    
    The interrupt message tells the user to press NEXT to continue diagnosis.
    """
    # Get the last AI message to include in the interrupt
    last_msg = state.messages[-1]
    
    # Determine the step context for the interrupt message
    step_context = f"Step {state.current_step} of {state.total_steps}"
    if state.step_description:
        step_context += f": {state.step_description}"
    
    # Create a clear instruction message - MUST say "Press NEXT to continue diagnosis"
    instruction = (
        f"{step_context} - Measurement complete. "
        "Press NEXT to continue diagnosis"
    )
    
    # Use interrupt to pause and wait for human
    # The human's response will be passed to resume_from_human
    human_response = interrupt({
        "instruction": instruction,
        "current_step": state.current_step,
        "total_steps": state.total_steps,
        "measurements_taken": len(state.measurements)
    })
    
    # This code only runs after interrupt resumes
    return {
        "is_paused_for_human": False
    }


def resume_from_human(state: ConversationalAgentState):
    """
    Resume from human interruption.
    This node processes the user's "next" response and continues the diagnosis.
    """
    # Get the last human message
    last_msg = state.messages[-1]
    
    # Extract user response
    user_response = ""
    if isinstance(last_msg, HumanMessage):
        if isinstance(last_msg.content, str):
            user_response = last_msg.content.strip().lower()
        elif isinstance(last_msg.content, list):
            for block in last_msg.content:
                if isinstance(block, dict) and block.get("type") == "text":
                    user_response = block.get("text", "").strip().lower()
                    break
    
    # Check if user wants to continue
    if "next" in user_response or "continue" in user_response:
        # Increment step counter
        return {
            "is_paused_for_human": False,
            "current_step": state.current_step + 1
        }
    else:
        # User provided other input - let agent handle it
        return {
            "is_paused_for_human": False
        }


# =============================================================================
# ROUTING
# =============================================================================

def should_continue(state: ConversationalAgentState):
    """
    Route after agent node - checks for session completion or max iterations.
    
    AUTONOMOUS FLOW: No more waiting for human confirmation.
    After agent decides on next action, we either:
    - Call tools (if needed)
    - Diagnose (if max iterations reached)
    - End (if session complete)
    
    The flow continues automatically without human "next" confirmation.
    """
    # Defensive: handle empty messages
    if not state.messages:
        return "tools"  # Default to tools if no messages
    
    # Check if session is complete
    if state.is_session_complete:
        return END
    
    # NOTE: We no longer pause for human confirmation
    # The is_paused_for_human flag is still tracked for backward compatibility
    # but we don't route to wait_for_human anymore
    
    # Check if we've exceeded max iterations - force diagnose
    if state.iteration_count >= MAX_ITERATIONS:
        return "diagnose"
    
    last_msg = state.messages[-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "tools"
        
    return END


def post_tool_route(state: ConversationalAgentState):
    """
    Route after tools node - ALWAYS pause for human after measurements.
    
    STRICT DIAGNOSTIC RULE: After EVERY measurement, we MUST pause for user confirmation.
    
    - If read_multimeter returns "success" → route to wait_for_human (PAUSE REQUIRED)
    
    - If read_multimeter returns "timeout" or "timeout_unstable" → route to wait_for_human
      (User will confirm retry or continue)
    
    - If fault detected → route to wait_for_human (User will confirm diagnosis)
    
    The key change: After any measurement, we ALWAYS pause for human "next" confirmation.
    The agent must not auto-proceed - must wait for user to press NEXT.
    """
    # Defensive: handle empty messages
    if not state.messages:
        return "agent"
    
    # After tools run, check if this was a measurement tool
    last_msg = state.messages[-1]
    
    # Check if last tool was a measurement
    if isinstance(last_msg, ToolMessage):
        try:
            result = json.loads(last_msg.content)
            if isinstance(result, dict):
                # Check for measurement status
                status = result.get("status", "")
                
                # Handle timeout cases - still pause for human to confirm retry
                if status in ("timeout", "timeout_unstable"):
                    return "wait_for_human"
                
                # Handle success - PAUSE FOR HUMAN before continuing
                # This is the KEY CHANGE: always pause after measurements
                if status == "success" or "value" in result:
                    return "wait_for_human"
        except:
            pass
    
    # For non-measurement tools, continue to agent
    return "agent"


def handle_timeout_node(state: ConversationalAgentState):
    """
    Handle timeout from read_multimeter.
    
    AUTONOMOUS FLOW: Instead of asking user to type something specific,
    we provide guidance and let the agent decide next steps.
    
    The agent will:
    1. Explain the situation to the user
    2. Offer to retry or accept manual input
    3. Continue the diagnostic flow
    
    We no longer use interrupt() - we just return and let the agent
    handle the retry logic naturally.
    """
    last_msg = state.messages[-1]
    test_point = "unknown"
    guidance_info = None
    
    # Get test point and guidance from the timeout result
    if isinstance(last_msg, ToolMessage):
        try:
            result = json.loads(last_msg.content)
            test_point = result.get("test_point", "unknown")
            guidance_info = result.get("guidance")
        except:
            pass
    
    # NO INTERRUPT - just continue to agent to handle retry
    # The agent will see the timeout status and can:
    # - Call read_multimeter again for retry
    # - Call enter_manual_reading
    # - Provide guidance to the user
    
    return {
        "is_paused_for_human": False,
        "last_tool_result": {
            "status": "timeout_handled",
            "test_point": test_point,
            "guidance_available": guidance_info is not None
        }
    }

# =============================================================================
# DIAGNOSE NODE - Provides diagnosis when max iterations reached
# =============================================================================

def diagnose_node(state: ConversationalAgentState):
    """
    Diagnose node that provides final analysis when max iterations reached.
    This node analyzes accumulated measurements and provides a conclusion.
    """
    from src.infrastructure.llm_manager import invoke_with_retry
    from langchain_core.messages import SystemMessage
    
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
    
    # Use retry logic for diagnosis (handles RateLimitError, APIError, etc.)
    response = invoke_with_retry([{"role": "system", "content": diagnose_prompt}])
    
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
    """Build the custom interactive graph with human-in-the-loop support."""
    builder = StateGraph(ConversationalAgentState)
    
    # Add all nodes
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tool_node)
    builder.add_node("diagnose", diagnose_node)
    builder.add_node("wait_for_human", wait_for_human)
    builder.add_node("resume_from_human", resume_from_human)
    builder.add_node("handle_timeout", handle_timeout_node)
    
    # Start at agent
    builder.add_edge(START, "agent")
    
    # Agent node routing: tools, diagnose, wait_for_human, or END
    builder.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "diagnose": "diagnose",
            "wait_for_human": "wait_for_human",
            END: END
        }
    )
    
    # Tools routing: after measurement, ALWAYS pause for human confirmation
    # This implements the strict diagnostic rule: "Press NEXT to continue diagnosis"
    builder.add_conditional_edges(
        "tools",
        post_tool_route,
        {
            "agent": "agent",
            "wait_for_human": "wait_for_human",
            "handle_timeout": "handle_timeout"
        }
    )
    
    # After waiting for human, resume processing
    builder.add_edge("wait_for_human", "resume_from_human")
    builder.add_edge("resume_from_human", "agent")
    
    # After timeout handling, resume to agent to process user response
    builder.add_edge("handle_timeout", "resume_from_human")
    
    # Final edges
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
