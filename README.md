# emailchecking

Travel confirmations end up spread over two inboxes: flights and hotels in a personal
Gmail account, and conference or department travel in the university mailbox. This
project reads both, filters out the marketing mail, works out which messages describe
an actual trip, and puts them on a single timeline that also flags clashes like
overlapping bookings.

- [`backend/`](backend/README.md): Python. Mailbox sync, normalization and dedup, a
  three-stage classifier with schema validation and a rule-based fallback, event
  extraction and conflict detection. Stores everything in SQLite.
- [`apple-app/`](apple-app/README.md): SwiftUI client for iOS and macOS that shows the
  timeline and lets you correct events locally.

## Status

The pipeline runs end to end against stubbed mailbox APIs and a rule-based stand-in for
the model. Real OAuth token exchange, the Gmail/Graph HTTP clients, an LLM-backed stage
runner and an HTTP server in front of `calendar/api.py` are still missing.

## Quick start

```bash
cd backend && python3 -m unittest discover -s tests -p "test_*.py"
cd ../apple-app && swift test && swift run TripCalendarApp
```
