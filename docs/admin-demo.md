# Vehicle and maintenance demo

Prepared on 4 November 2026 using the existing catalogue and uploaded manuals.

- All 10 catalogue vehicles have active vehicle/model/manufacturer selections and enabled chatbot scopes.
- The six published learning topics have chatbot scopes enabled. The archived test topic stays archived.
- Eight additional indexed vehicle documents were published through the normal publication checks.
- 175 source-backed service rules were added across 10 vehicle schedules. Eight schedules are published; two remain drafts because their source manuals failed processing.
- No accounts, personal garage entries or service history were created. Tasks without a checked interval remain unset.

In the admin, open **Service Task Library** and choose a vehicle to see its intervals. Each interval links to its task in **Service Schedules**, with its original document/page and editing controls. Published schedules require a new draft revision before editing. Drafts are labelled separately from instructions available to drivers.

For a fuller maintenance demonstration, use **Perodua Myvi 2021**: it has 22 sourced rules and a published manual. In the phone app, add that catalogue vehicle and enter its mileage. Manufacturer tasks are supplied by the published schedule. Log a service date and mileage to establish the previous-service baseline; the app deliberately shows “Information required” when it cannot calculate a due date from saved facts. Conditional tasks still require checking their equipment/usage conditions.

The imported schedules cover a checked subset of normal-use maintenance. Notes retain initial-service exceptions, severe-use guidance and equipment restrictions. Irregular coolant replacements and unresolved engine/transmission alternatives are informational rules rather than invented repeating intervals. Review the original manual before extending coverage.

## Remaining source work

| Vehicle | Issue | Current result |
| --- | --- | --- |
| Axia 2014 | Owner-manual OCR checkpoint refers to a missing Windows OCR task (404). | Vehicle enabled; schedule saved as a draft. |
| Alza 2022 | Owner-manual OCR checkpoint refers to a missing Windows OCR task (404). | Vehicle and ready supplementary documents enabled; schedule saved as a draft. |
| Saga 2022 | Owner-manual extraction upload exceeded the Storage size limit (413). | Vehicle enabled; service rules use the successfully processed warranty/service booklet. |

Repair these documents through Reference Library before publishing the two remaining schedules. Do not mark failed indexing as successful. Intervals missing from the checked sources remain unset for review.

## Reproducible preparation

`scripts/data/admin_maintenance_intervals.json` records the exact vehicle codes, source revisions, PDF pages, task names and checked instructions. The importer refuses changed source revisions and preserves every existing schedule, including edits or withdrawals.

```sh
.venv/bin/python -m scripts.prepare_admin_demo
.venv/bin/python -m scripts.prepare_admin_demo --apply
```

The first command previews changes. Applying saves a catalogue/content snapshot under `output/admin-demo/before-*.json` before changing any records and writes an import report there. These snapshots contain no account or personal maintenance tables. The live verification results are in `output/admin-demo/verification.json`.
