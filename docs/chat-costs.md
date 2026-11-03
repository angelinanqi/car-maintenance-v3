# Saved service costs in chat

The chatbot receives saved service costs for the signed-in user's active vehicle.
Amounts use MYR and are displayed as RM. No database migration or client UI update
is needed; deploy the backend and private RAG service together for the shared contract.

Supported questions include “How much did my last oil change cost?” and “How much
have I recorded in maintenance spending for this car?” Answers use the existing
Saved maintenance records citation.

The backend calculates the all-records total with decimal arithmetic before any
history limits. It also supplies counts of records with and without costs. Unknown
costs remain null; a saved zero is free. An all-unknown history must not be described
as zero actual spending. Totals cover recorded amounts, not unrecorded expenditure.

Latest services for tracked tasks and standalone titles include their costs. Up to
50 individual recent records are also supplied, newest first. The context budget
may omit further history; coverage flags disclose this while retaining the complete
spending summary. Overlapping latest-service and recent-history entries must never
be summed together.

Period/category totals, averages, price differences, live quotations and future
estimates are not provided. The model is instructed to explain unavailable
aggregates rather than calculate them from partial history. Notes, receipts and
workshop details remain outside this personal context.

Run the focused checks with:

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_chat_costs.py'
```
