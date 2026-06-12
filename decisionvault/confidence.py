import re


def normalize_for_duplicate_check(value):
    return str(value or "").strip().lower()


def get_duplicate_key(record):
    decision_text = normalize_for_duplicate_check(record.get("decision"))
    affected_area = normalize_for_duplicate_check(
        record.get("affected_project_or_workflow")
    )
    return (decision_text, affected_area)


def has_meaningful_value(value):
    text = str(value or "").strip().lower()
    return text and text not in {"n/a", "none", "unknown", "not specified"}


def update_probability_with_evidence(probability, likelihood_if_true, likelihood_if_false):
    probability = min(max(probability, 0.01), 0.99)
    prior_odds = probability / (1 - probability)
    likelihood_ratio = likelihood_if_true / likelihood_if_false
    posterior_odds = prior_odds * likelihood_ratio

    return posterior_odds / (1 + posterior_odds)


def get_unique_source_count(source_evidence):
    source_names = set()

    for evidence in source_evidence:
        for source_name in re.findall(r"\(([^()]+\.(?:txt|md|csv))\)", str(evidence)):
            source_names.add(source_name.lower())

    return len(source_names)


def calculate_bayesian_confidence(record):
    probability = 0.60
    factors = ["Started from a 60% prior for an extracted decision being valid."]

    source_evidence = record.get("source_evidence", [])
    if not isinstance(source_evidence, list):
        source_evidence = []

    evidence_count = len([item for item in source_evidence if str(item).strip()])
    unique_source_count = get_unique_source_count(source_evidence)
    combined_text = " ".join(
        str(record.get(field, ""))
        for field in [
            "decision",
            "reason",
            "approver",
            "reusable_context"
        ]
    )
    combined_text += " " + " ".join(str(item) for item in source_evidence)
    combined_text = combined_text.lower()

    if evidence_count >= 4:
        probability = update_probability_with_evidence(probability, 0.90, 0.35)
        factors.append("Strong boost: four or more evidence snippets support it.")
    elif evidence_count >= 2:
        probability = update_probability_with_evidence(probability, 0.78, 0.45)
        factors.append("Boost: multiple evidence snippets support it.")
    elif evidence_count == 1:
        probability = update_probability_with_evidence(probability, 0.62, 0.55)
        factors.append("Small boost: at least one evidence snippet supports it.")
    else:
        probability = update_probability_with_evidence(probability, 0.30, 0.80)
        factors.append("Penalty: no source evidence was captured.")

    if unique_source_count >= 2:
        probability = update_probability_with_evidence(probability, 0.82, 0.40)
        factors.append("Boost: evidence appears across multiple source files.")

    if has_meaningful_value(record.get("owner")):
        probability = update_probability_with_evidence(probability, 0.74, 0.50)
        factors.append("Boost: a decision owner is present.")
    else:
        probability = update_probability_with_evidence(probability, 0.40, 0.70)
        factors.append("Penalty: no clear owner was found.")

    if has_meaningful_value(record.get("approver")):
        probability = update_probability_with_evidence(probability, 0.76, 0.50)
        factors.append("Boost: approval or agreement context is present.")
    else:
        probability = update_probability_with_evidence(probability, 0.45, 0.68)
        factors.append("Penalty: no approver or agreement context was found.")

    approval_terms = [
        "approved",
        "approval",
        "agreed",
        "confirmed",
        "sign off",
        "signed off",
        "decided",
        "final"
    ]
    ambiguity_terms = [
        "maybe",
        "tentative",
        "not sure",
        "unclear",
        "pending",
        "blocked",
        "depends",
        "waiting"
    ]

    if any(term in combined_text for term in approval_terms):
        probability = update_probability_with_evidence(probability, 0.80, 0.46)
        factors.append("Boost: explicit decision or approval language was found.")

    if any(term in combined_text for term in ambiguity_terms):
        probability = update_probability_with_evidence(probability, 0.42, 0.75)
        factors.append("Penalty: ambiguity or unresolved-dependency language was found.")

    if not has_meaningful_value(record.get("reason")):
        probability = update_probability_with_evidence(probability, 0.48, 0.68)
        factors.append("Penalty: the rationale is missing or unclear.")

    score = round(probability * 100)

    if score >= 80:
        level = "High"
    elif score >= 60:
        level = "Medium"
    else:
        level = "Low"

    return {
        "score": score,
        "level": level,
        "factors": factors
    }


def add_bayesian_confidence(record):
    enriched_record = record.copy()
    bayes_result = calculate_bayesian_confidence(enriched_record)

    enriched_record["bayesian_confidence_score"] = bayes_result["score"]
    enriched_record["bayesian_confidence_level"] = bayes_result["level"]
    enriched_record["bayesian_confidence_factors"] = bayes_result["factors"]

    return enriched_record


def add_bayesian_confidence_to_records(records):
    records = records or []
    return [add_bayesian_confidence(record) for record in records]
