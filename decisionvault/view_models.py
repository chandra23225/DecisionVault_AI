from decisionvault.confidence import has_meaningful_value
from decisionvault.validation import get_file_size


REQUIRED_RECORD_FIELDS = [
    "decision",
    "reason",
    "owner",
    "approver",
    "affected_project_or_workflow",
    "source_evidence",
]


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


def get_missing_record_fields(record):
    return [
        field for field in REQUIRED_RECORD_FIELDS
        if not field_has_value(record, field)
    ]


def get_record_quality(record):
    missing_fields = get_missing_record_fields(record)
    present_count = len(REQUIRED_RECORD_FIELDS) - len(missing_fields)
    score = round((present_count / len(REQUIRED_RECORD_FIELDS)) * 100)

    if score >= 85:
        level = "Ready"
    elif score >= 65:
        level = "Review"
    else:
        level = "Incomplete"

    return {
        "score": score,
        "level": level,
        "missing_fields": missing_fields,
    }


def enrich_records_for_ui(records):
    enriched_records = []

    for record in records or []:
        enriched_record = record.copy()
        quality = get_record_quality(enriched_record)
        enriched_record["record_quality_score"] = quality["score"]
        enriched_record["record_quality_level"] = quality["level"]
        enriched_record["record_missing_fields"] = quality["missing_fields"]
        enriched_records.append(enriched_record)

    return enriched_records


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
