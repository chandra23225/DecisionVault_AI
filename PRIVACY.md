# Data Safety Notes

DecisionVault AI sends uploaded text to Gemini through the configured API key. Treat uploaded files as data that leaves the local machine for model processing.

## Before Using Real Workplace Data

Use anonymized or approved data unless your organization has explicitly approved the API setup for confidential use.

Remove or replace:

- Customer names and account IDs
- Employee personal details beyond role/name needed for testing
- Email addresses and phone numbers
- API keys, passwords, tokens, and URLs with secrets
- Contract terms, pricing, financial records, or regulated data
- Legal, medical, HR, or compliance-sensitive information

## Recommended Anonymization Pattern

Replace specific entities with stable placeholders:

```text
Priya Shah -> Product Lead
Amit Rao -> Engineering Manager
acme-customer-9182 -> Customer A
payments-prod-east-2 -> Production service
```

The app works best when decision context is preserved while sensitive identifiers are removed.

## MVP Scope

This repository uses local JSON storage and does not include authentication, access control, encryption, or production data governance. Use it as a demo/MVP unless those controls are added.
