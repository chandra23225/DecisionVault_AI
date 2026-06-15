import json

from google import genai
from google.genai import types

from decisionvault.gemini_helpers import GeminiAPIError, GeminiJSONError, extract_json_from_response


EXTRACTION_MODEL = "gemini-2.5-flash"


def build_extraction_prompt(text):
    return f"""
You are DecisionVault AI, a GenAI system that extracts structured business decisions
from messy workplace communication.

Your goal is NOT to list every sentence as a decision.

Your goal is to identify the main business decisions and organize supporting details
under each decision.

IMPORTANT RULES:

1. A "decision" is a final or agreed business choice.
   Examples:
   - Delay launch to next Friday
   - Choose Vendor B
   - Remove a feature from MVP
   - Pause deployment until approval

2. A "follow-up action" is NOT a separate decision unless it represents a new business choice.
   Example:
   - "Ramesh will update Jira" is a follow-up action, not a separate decision.

3. A "dependency" or "condition" is NOT a separate decision.
   Example:
   - "Finance approval is pending" is a dependency/reason, not a decision.

4. Group related details into one decision record when they belong to the same situation.

5. Prefer fewer, higher-quality decision records over many small records.

6. If something is only an update, blocker, or task, include it under the relevant decision as
   reason, dependency, follow-up, or evidence.

For each main decision, return:
- decision
- decision_type
- reason
- owner
- approver
- affected_project_or_workflow
- dependencies_or_conditions
- follow_up_actions
- source_evidence
- confidence
- reusable_context

Return ONLY valid JSON in this exact format:

{{
  "executive_summary": "short summary of the main decisions found",
  "decision_records": [
    {{
      "decision": "...",
      "decision_type": "Timeline Change / Approval / Scope Change / Vendor Choice / Process Exception / Deployment Condition / Other",
      "reason": "...",
      "owner": "...",
      "approver": "...",
      "affected_project_or_workflow": "...",
      "dependencies_or_conditions": ["..."],
      "follow_up_actions": ["..."],
      "source_evidence": ["..."],
      "confidence": "High/Medium/Low",
      "reusable_context": "..."
    }}
  ],
  "items_needing_human_review": [
    {{
      "item": "...",
      "why_review_needed": "..."
    }}
  ]
}}

Workplace text:
{text}
"""


def create_gemini_client(api_key):
    return genai.Client(api_key=api_key)


def extract_decisions_with_client(client, text):
    try:
        response = client.models.generate_content(
            model=EXTRACTION_MODEL,
            contents=build_extraction_prompt(text),
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
    except Exception as exc:
        raise GeminiAPIError(f"Gemini request failed: {exc}", exc) from exc

    raw_output = response.text or ""

    try:
        return extract_json_from_response(raw_output)
    except json.JSONDecodeError as e:
        raise GeminiJSONError(str(e), raw_output) from e


def build_ask_context_text(context):
    context = context or {}
    executive_summary = str(context.get("executive_summary") or "").strip()
    source_text = str(context.get("source_text") or "").strip()

    if not executive_summary and not source_text:
        return "No additional meeting context was provided."

    parts = []

    if executive_summary:
        parts.append(f"Executive summary:\n{executive_summary}")

    if source_text:
        parts.append(f"Uploaded source text:\n{source_text[:12000]}")

    return "\n\n".join(parts)


def normalize_ask_answer(answer):
    answer = answer or {}

    normalized = {
        "answer_status": answer.get("answer_status") or "Answered",
        "answer_source": answer.get("answer_source") or "Not Available",
        "confidence": answer.get("confidence") or "Medium",
        "direct_answer": answer.get("direct_answer") or "",
        "key_points": answer.get("key_points") or [],
        "supporting_records": answer.get("supporting_records") or [],
        "source_references": answer.get("source_references") or [],
        "information_gaps": answer.get("information_gaps") or [],
        "recommended_next_steps": answer.get("recommended_next_steps") or [],
    }

    for list_field in [
        "key_points",
        "supporting_records",
        "source_references",
        "information_gaps",
        "recommended_next_steps",
    ]:
        if not isinstance(normalized[list_field], list):
            normalized[list_field] = [normalized[list_field]]

    return normalized


def ask_decision_vault_with_client(client, question, decision_records, context=None):
    prompt = f"""
You are DecisionVault AI.

You answer questions using ONLY the reviewed decision records and meeting context below.
Do not invent information that is not in those inputs.

Answering strategy:
1. Use reviewed decision records first when they contain the answer.
2. Use raw source text as backup for details not captured in reviewed records.
3. Use both when the best answer needs reviewed decisions plus meeting/source context.
4. If the answer is not present in either place, say it is not available.
5. Be useful for broad questions, including topic, summary, timeline, participants,
   owners, risks, approvals, blockers, follow-ups, open questions, and evidence.

Use the meeting context for broad questions about the meeting, such as its topic,
summary, source material, or overall discussion. Use the decision records for
questions about decisions, owners, approvals, workflows, evidence, and follow-ups.

Return ONLY valid JSON in this exact format:

{{
  "answer_status": "Answered / Partially Answered / Not Available",
  "answer_source": "Reviewed Records / Source Text / Both / Not Available",
  "confidence": "High / Medium / Low",
  "direct_answer": "A clear executive-ready answer in 2-4 sentences.",
  "key_points": ["short point", "short point"],
  "supporting_records": [
    {{
      "decision": "decision text",
      "owner": "owner if available",
      "workflow": "workflow if available",
      "evidence": ["source evidence or reason from the record"]
    }}
  ],
  "source_references": ["short quote or source detail from the raw text or summary"],
  "information_gaps": ["missing context, if any"],
  "recommended_next_steps": ["practical next step, if any"]
}}

If the answer is not available, set answer_status to "Not Available",
direct_answer to "That information is not available in the current decision memory.",
answer_source to "Not Available", confidence to "Low", and explain what is missing
in information_gaps.

Reviewed Decision Records:
{json.dumps(decision_records, indent=2)}

Meeting Context:
{build_ask_context_text(context)}

User Question:
{question}

Give a clear, concise answer.
"""

    try:
        response = client.models.generate_content(
            model=EXTRACTION_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
    except Exception as exc:
        raise GeminiAPIError(f"Gemini request failed: {exc}", exc) from exc

    raw_output = response.text or ""

    try:
        return normalize_ask_answer(extract_json_from_response(raw_output))
    except json.JSONDecodeError:
        return normalize_ask_answer({
            "answer_status": "Answered",
            "answer_source": "Both",
            "confidence": "Medium",
            "direct_answer": raw_output,
            "key_points": [],
            "supporting_records": [],
            "source_references": [],
            "information_gaps": [],
            "recommended_next_steps": [],
        })
