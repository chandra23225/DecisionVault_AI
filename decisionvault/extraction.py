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


def ask_decision_vault_with_client(client, question, decision_records):
    prompt = f"""
You are DecisionVault AI.

You answer questions using ONLY the provided decision records.
Do not invent information that is not in the records.

Return ONLY valid JSON in this exact format:

{{
  "answer_status": "Answered / Partially Answered / Not Available",
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
  "information_gaps": ["missing context, if any"],
  "recommended_next_steps": ["practical next step, if any"]
}}

If the answer is not available, set answer_status to "Not Available",
direct_answer to "That information is not available in the current decision memory.",
and explain what is missing in information_gaps.

Decision Records:
{json.dumps(decision_records, indent=2)}

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
        return extract_json_from_response(raw_output)
    except json.JSONDecodeError:
        return {
            "answer_status": "Answered",
            "direct_answer": raw_output,
            "key_points": [],
            "supporting_records": [],
            "information_gaps": [],
            "recommended_next_steps": [],
        }
