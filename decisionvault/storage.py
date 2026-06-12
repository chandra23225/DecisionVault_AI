import json
import os
import re
from datetime import datetime

from decisionvault.confidence import (
    add_bayesian_confidence_to_records,
    get_duplicate_key,
)


def load_vault(vault_file):
    if not os.path.exists(vault_file):
        return []

    try:
        with open(vault_file, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return []


def save_vault(records, vault_file):
    vault_dir = os.path.dirname(vault_file)

    if vault_dir:
        os.makedirs(vault_dir, exist_ok=True)

    with open(vault_file, "w", encoding="utf-8") as file:
        json.dump(records, file, indent=2)


def generate_decision_id(existing_records):
    highest_number = 0

    for record in existing_records:
        decision_id = str(record.get("decision_id", ""))
        match = re.match(r"DV-(\d+)$", decision_id)

        if match:
            highest_number = max(highest_number, int(match.group(1)))

    next_number = highest_number + 1
    return f"DV-{next_number:03d}"


def save_decisions_to_vault(decision_records, vault_file):
    existing_records = load_vault(vault_file)
    decision_records = add_bayesian_confidence_to_records(decision_records)
    existing_keys = {
        get_duplicate_key(record)
        for record in existing_records
    }

    saved_count = 0
    duplicate_count = 0
    duplicate_records = []

    for record in decision_records:
        duplicate_key = get_duplicate_key(record)

        if duplicate_key in existing_keys:
            duplicate_count += 1
            duplicate_records.append(record)
            continue

        new_record = record.copy()

        new_record["decision_id"] = generate_decision_id(existing_records)
        new_record["saved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_record["status"] = "Active"

        existing_records.append(new_record)
        existing_keys.add(duplicate_key)
        saved_count += 1

    save_vault(existing_records, vault_file)

    return saved_count, duplicate_count, duplicate_records


def delete_decision_from_vault(decision_id, vault_file):
    existing_records = load_vault(vault_file)
    remaining_records = [
        record for record in existing_records
        if record.get("decision_id") != decision_id
    ]

    if len(remaining_records) == len(existing_records):
        return False

    save_vault(remaining_records, vault_file)
    return True
