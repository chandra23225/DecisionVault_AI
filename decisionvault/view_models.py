from decisionvault.confidence import has_meaningful_value
from decisionvault.validation import get_file_size


REQUIRED_RECORD_FIELDS = [
    "decision",
    "reason",
    "owner",
    "affected_project_or_workflow",
    "source_evidence",
]

APPROVER_REQUIRED_TERMS = [
    "approval",
    "approved",
    "approver",
    "sign off",
    "signed off",
    "deployment condition",
    "production deployment",
    "compliance",
]

FIELD_LABELS = {
    "affected_project_or_workflow": "workflow",
    "source_evidence": "source evidence",
}

FIELD_PLACEHOLDERS = {
    "owner": "Owner not found",
    "approver": "Approver not found",
    "affected_project_or_workflow": "Workflow not found",
    "reason": "Reason not found",
    "decision_type": "Type not found",
    "confidence": "Confidence not found",
    "reusable_context": "Reusable context not found",
}


def format_bytes(size):
    size = int(size or 0)

    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"

    if size >= 1024:
        return f"{size / 1024:.1f} KB"

    return f"{size} B"


def ensure_list(value):
    if isinstance(value, list):
        return value

    if value is None:
        return []

    return [value]


def field_has_value(record, field):
    value = record.get(field)

    if isinstance(value, list):
        return any(has_meaningful_value(item) for item in value)

    return has_meaningful_value(value)


def is_approver_required(record):
    decision_type = str(record.get("decision_type") or "").lower()
    combined_text = " ".join(
        str(record.get(field, ""))
        for field in [
            "decision",
            "reason",
            "reusable_context",
            "affected_project_or_workflow",
        ]
    ).lower()
    combined_text += " " + " ".join(str(item) for item in ensure_list(record.get("source_evidence")))

    return (
        "approval" in decision_type
        or "deployment condition" in decision_type
        or any(term in combined_text for term in APPROVER_REQUIRED_TERMS)
    )


def get_missing_record_fields(record):
    missing_fields = [
        field for field in REQUIRED_RECORD_FIELDS
        if not field_has_value(record, field)
    ]

    if is_approver_required(record) and not field_has_value(record, "approver"):
        missing_fields.append("approver")

    return missing_fields


def get_optional_missing_record_fields(record):
    if is_approver_required(record) or field_has_value(record, "approver"):
        return []

    return ["approver"]


def get_record_quality(record):
    missing_fields = get_missing_record_fields(record)
    present_count = len(REQUIRED_RECORD_FIELDS) - len(missing_fields)
    score = round((present_count / len(REQUIRED_RECORD_FIELDS)) * 100)

    if score >= 85:
        level = "Ready"
    elif score >= 60:
        level = "Review"
    else:
        level = "Incomplete"

    return {
        "score": score,
        "level": level,
        "missing_fields": missing_fields,
        "optional_missing_fields": get_optional_missing_record_fields(record),
    }


def get_friendly_form_field(record, field):
    value = record.get(field)

    return {
        "value": value if has_meaningful_value(value) else "",
        "placeholder": FIELD_PLACEHOLDERS.get(field, f"{field.replace('_', ' ').title()} not found"),
    }


def get_record_form_fields(record):
    return {
        "decision_type": get_friendly_form_field(record, "decision_type"),
        "confidence": get_friendly_form_field(record, "confidence"),
        "owner": get_friendly_form_field(record, "owner"),
        "approver": get_friendly_form_field(record, "approver"),
        "workflow": get_friendly_form_field(record, "affected_project_or_workflow"),
        "reason": get_friendly_form_field(record, "reason"),
        "reusable_context": get_friendly_form_field(record, "reusable_context"),
    }


def format_missing_field_warning(missing_fields):
    missing_fields = missing_fields or []

    if not missing_fields:
        return ""

    labels = [
        FIELD_LABELS.get(field, field.replace("_", " "))
        for field in missing_fields
    ]

    if len(labels) == 1:
        field_text = labels[0]
    else:
        field_text = ", ".join(labels[:-1]) + f" and {labels[-1]}"

    return f"Needs review: {field_text} not found"


def format_optional_missing_field_note(optional_missing_fields):
    optional_missing_fields = optional_missing_fields or []

    if not optional_missing_fields:
        return ""

    labels = [
        FIELD_LABELS.get(field, field.replace("_", " "))
        for field in optional_missing_fields
    ]

    if len(labels) == 1:
        field_text = labels[0]
    else:
        field_text = ", ".join(labels[:-1]) + f" and {labels[-1]}"

    return f"Optional: {field_text} not found"


def enrich_records_for_ui(records):
    enriched_records = []

    for record in records or []:
        enriched_record = record.copy()
        quality = get_record_quality(enriched_record)
        enriched_record["record_quality_score"] = quality["score"]
        enriched_record["record_quality_level"] = quality["level"]
        enriched_record["record_missing_fields"] = quality["missing_fields"]
        enriched_record["record_optional_missing_fields"] = quality["optional_missing_fields"]
        enriched_record["record_missing_field_warning"] = (
            format_missing_field_warning(quality["missing_fields"])
            or format_optional_missing_field_note(quality["optional_missing_fields"])
        )
        enriched_record["form_fields"] = get_record_form_fields(enriched_record)
        enriched_records.append(enriched_record)

    return enriched_records


def get_unique_meaningful_values(records, field, limit=3):
    values = []
    seen = set()

    for record in records or []:
        value = str(record.get(field) or "").strip()
        key = value.lower()

        if has_meaningful_value(value) and key not in seen:
            values.append(value)
            seen.add(key)

        if len(values) >= limit:
            break

    return values


def generate_example_questions(records):
    records = records or []
    questions = [
        "What were the main decisions?",
        "What is the topic of this meeting?",
        "What are the risks or blockers?",
        "What follow-up actions are needed?",
    ]

    owners = get_unique_meaningful_values(records, "owner", limit=1)
    workflows = get_unique_meaningful_values(records, "affected_project_or_workflow", limit=1)

    if owners:
        questions.append(f"What follow-ups does {owners[0]} own?")

    if any(
        is_approver_required(record) and not field_has_value(record, "approver")
        for record in records
    ):
        questions.append("What approvals are missing?")

    if workflows:
        questions.append(f"What decisions affect {workflows[0]}?")

    return questions[:7]


def filter_records_for_vault(records, query="", status=""):
    query = str(query or "").strip().lower()
    status = str(status or "").strip()
    filtered_records = []

    for record in records or []:
        searchable_text = " ".join(
            str(record.get(field, ""))
            for field in [
                "decision",
                "owner",
                "approver",
                "affected_project_or_workflow",
                "reason",
                "status",
                "decision_id",
            ]
        ).lower()

        if query and query not in searchable_text:
            continue

        if status and record.get("status") != status:
            continue

        filtered_records.append(record)

    return filtered_records


def summarize_records(records):
    records = records or []

    if not records:
        return {
            "total": 0,
            "ready": 0,
            "review": 0,
            "incomplete": 0,
            "average_quality_score": 0,
            "average_bayes_score": 0,
        }

    enriched_records = enrich_records_for_ui(records)

    return {
        "total": len(enriched_records),
        "ready": sum(
            1 for record in enriched_records
            if record.get("record_quality_level") == "Ready"
        ),
        "review": sum(
            1 for record in enriched_records
            if record.get("record_quality_level") == "Review"
        ),
        "incomplete": sum(
            1 for record in enriched_records
            if record.get("record_quality_level") == "Incomplete"
        ),
        "average_quality_score": round(
            sum(
                int(record.get("record_quality_score", 0))
                for record in enriched_records
            ) / len(enriched_records)
        ),
        "average_bayes_score": round(
            sum(
                int(record.get("bayesian_confidence_score", 0))
                for record in enriched_records
            ) / len(enriched_records)
        ),
    }


def summarize_uploaded_files(files):
    files = files or []
    total_size = sum(get_file_size(file) for file in files)

    return {
        "count": len(files),
        "total_size": total_size,
        "total_size_label": format_bytes(total_size),
        "files": [
            {
                "name": file.name,
                "size": get_file_size(file),
                "size_label": format_bytes(get_file_size(file)),
            }
            for file in files
        ],
    }
