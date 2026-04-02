import json
import os

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from src.state import NOCAgentState, SafetyAuditResult
from src.retriever import retrieve_relevant_sops

# ---------------------------------------------------------------------------
# Module-level resources — patchable in tests
# ---------------------------------------------------------------------------

llm = ChatOpenAI(
    model="deepseek-chat",
    temperature=0.1,
    openai_api_key=os.getenv("DEEPSEEK_API_KEY"),
    openai_api_base="https://api.deepseek.com"
)


# =============================================================================
# NODE 1: Telemetry Checker
# =============================================================================


def check_network(state: NOCAgentState) -> dict:
    """Fetch live device telemetry from local JSON file for the given alarm."""
    print("\n" + "=" * 65)
    print("NODE 1: TELEMETRY CHECKER — Querying Live Network Data")
    print("=" * 65)
    print(f"   Alarm ID: {state['alarm_id']}")

    alarm_id = state["alarm_id"]
    try:
        with open("data/mock_telemetry.json", "r", encoding="utf-8") as f:
            telemetry_data = json.load(f)
        telemetry = telemetry_data.get(alarm_id, {})
        print(f"   Telemetry keys: {list(telemetry.keys()) if telemetry else 'none'}")
        return {"telemetry": telemetry if telemetry else {}}
    except Exception as e:
        print(f"   ERROR loading telemetry from JSON: {e}")
        return {"telemetry": {}}


# =============================================================================
# NODE 2: Document Retriever
# =============================================================================


def get_manuals(state: NOCAgentState) -> dict:
    """Retrieve the most relevant SOPs via semantic similarity search."""
    print("\n" + "=" * 65)
    print("NODE 2: DOCUMENT RETRIEVER — Querying SOP Vector Store")
    print("=" * 65)

    telemetry = state.get("telemetry", {})
    error_type = telemetry.get("error_type", state.get("error_message", ""))
    device = telemetry.get("device", "unknown device")
    location = telemetry.get("location", "unknown location")
    severity = telemetry.get("severity", "UNKNOWN")

    search_query = (
        f"{severity} alarm: {error_type} on {device} at {location}. "
        f"Original error: {state.get('error_message', '')}. "
        f"Need SOP for diagnosis, isolation, and remediation procedure."
    )

    iteration = state.get("iterations", 0)
    if iteration > 0:
        safety_feedback = state.get("safety_feedback", "")
        print(f"   REVISION LOOP — Iteration #{iteration}")
        search_query += f" Safety constraint violation: {safety_feedback[:200]}"

    print(f"   Search Query: {search_query[:100]}...")
    sop_results = retrieve_relevant_sops(search_query, top_k=3)
    print(f"   Retrieved {len(sop_results)} relevant SOP document(s).")

    return {"sops": sop_results}


# =============================================================================
# NODE 3: The Brain — Resolution Drafter
# =============================================================================


def draft_fix(state: NOCAgentState) -> dict:
    """Synthesize telemetry + SOPs into a structured resolution ticket (GPT-4o)."""
    print("\n" + "=" * 65)
    print("NODE 3: THE BRAIN — Drafting Resolution Ticket (GPT-4o)")
    print("=" * 65)

    iteration = state.get("iterations", 0)

    telemetry_str = json.dumps(state.get("telemetry", {}), indent=2)

    sops = state.get("sops", [])
    sops_str = "\n\n---\n\n".join(s.get("content", str(s)) if isinstance(s, dict) else s for s in sops)

    system_prompt = """You are an elite Level 3 Telecom Network Operations Center (NOC) Engineer
with 15+ years of experience in HFC cable networks, GPON fiber optics, and IP/MPLS core routing.

Your task is to analyze a live network alarm and produce a formal, step-by-step Incident Resolution Ticket.

CRITICAL RULES:
1. BASE EVERY STEP EXCLUSIVELY on the provided Standard Operating Procedures (SOPs) below.
2. DO NOT invent, add, or suggest any step not explicitly described in the SOPs.
3. DO NOT recommend rebooting or power-cycling unless the SOP explicitly permits it.
4. If the SOPs do not cover a required action, state that escalation is required."""

    human_content = f"""
LIVE NETWORK TELEMETRY DATA:
{telemetry_str}

RETRIEVED STANDARD OPERATING PROCEDURES:
{sops_str}

ORIGINAL ALARM:
Alarm ID: {state["alarm_id"]}
Error: {state.get("error_message", "")}
"""

    if iteration > 0 and state.get("resolution_ticket") and state.get("safety_feedback"):
        human_content += f"""

PREVIOUS DRAFT (FAILED SAFETY AUDIT — DO NOT REUSE):
{state["resolution_ticket"]}

CRITIC'S AUDIT FEEDBACK (MUST ADDRESS IN THIS REVISION):
{state["safety_feedback"]}

INSTRUCTION: Revise the ticket to strictly comply with the SOPs.
"""

    human_content += "\nDraft the Incident Resolution Ticket now:"

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_content),
    ]

    print("   Invoking GPT-4o for ticket generation...")
    response = llm.invoke(messages)
    resolution_ticket = response.content

    print(f"   Resolution ticket drafted ({len(resolution_ticket)} characters).")
    return {"resolution_ticket": resolution_ticket}


# =============================================================================
# NODE 4: The Critic — Safety Checker
# =============================================================================


def safety_check(state: NOCAgentState) -> dict:
    """Audit the resolution ticket for SOP compliance."""
    print("\n" + "=" * 65)
    print("NODE 4: THE CRITIC — Running Safety & SOP Compliance Audit")
    print("=" * 65)

    sops = state.get("sops", [])
    sops_str = "\n\n---\n\n".join(s.get("content", str(s)) if isinstance(s, dict) else s for s in sops)
    proposed_resolution = state.get("resolution_ticket", "")

    critic_system_prompt = """You are a strict NOC Safety Compliance Auditor.
Your ONLY job is to verify that a proposed network resolution ticket is 100% compliant
with the provided Standard Operating Procedures (SOPs).

Mark as SAFE ONLY if every single step is directly traceable to the SOPs.
Mark as UNSAFE if ANY step deviates from the SOPs.

Output format:
IS_SAFE: true or false
FEEDBACK: Your detailed feedback
"""

    critic_human_content = f"""
STANDARD OPERATING PROCEDURES (Ground Truth):
{sops_str}

PROPOSED RESOLUTION TICKET TO AUDIT:
{proposed_resolution}

Perform your compliance audit and return your verdict in the required format:"""

    messages = [
        SystemMessage(content=critic_system_prompt),
        HumanMessage(content=critic_human_content),
    ]

    print("   Invoking DeepSeek critic...")
    response = llm.invoke(messages)
    response_text = response.content

    # 解析响应
    is_safe = "IS_SAFE: true" in response_text.lower()
    feedback = response_text.split("FEEDBACK:")[-1].strip() if "FEEDBACK:" in response_text else "No feedback provided."

    print(f"   AUDIT RESULT: {'SAFE' if is_safe else 'UNSAFE'}")
    print(f"   Feedback: {feedback[:200]}...")

    current_iterations = state.get("iterations", 0)
    result: dict = {
        "is_safe": is_safe,
        "safety_feedback": feedback,
    }
    if not is_safe:
        result["iterations"] = current_iterations + 1

    return result
