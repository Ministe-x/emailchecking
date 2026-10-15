# Apple client

SwiftUI app (iOS 17 / macOS 14) that shows the trip timeline produced by the backend.
It is a Swift package with two targets:

- `TripCalendarCore`: models, networking, payload parsing, local corrections and view
  models. No SwiftUI, so all of it is unit-testable.
- `TripCalendarApp`: the SwiftUI screens.

## Screens

- **Accounts**: connection state of the Gmail and school mailboxes. This is local
  state only for now. The OAuth flow lives on the backend and isn't wired up to the app yet.
- **Sync**: time of the last fetch and how many events came back.
- **Timeline**: events grouped by day, with priority/confidence badges and red badges
  for conflicts reported by the backend.
- **Trip detail**: the source email and scores, plus manual corrections (confirm,
  ignore, or edit title/location/time). Corrections are stored in `UserDefaults` under
  `localCorrections.v1` and are not sent back to the backend yet.

## Running

```bash
cd apple-app
swift test
swift run TripCalendarApp      # macOS
```

For iOS, open `Package.swift` in Xcode and pick a simulator.

Without any configuration the app uses `MockTimelineService` (two fake Berlin events with
a conflict between them), which is handy for UI work. To use the real backend:

```bash
export TIMELINE_API_BASE_URL="http://127.0.0.1:8000"
export TIMELINE_API_PATH="/calendar/timeline"     # default
export TIMELINE_API_TIMEOUT_SECONDS="10"          # default
export TIMELINE_API_MAX_RETRIES="3"               # default
swift run TripCalendarApp
```

## Backend contract

```
GET {TIMELINE_API_BASE_URL}{TIMELINE_API_PATH}?accountEmail=<email>&limit=<n>
```

```json
{
  "events": [
    {
      "eventId": "evt_...", "title": "...", "start": "2026-11-20T15:00:00+00:00",
      "end": "...", "timezone": "UTC+00:00", "location": null, "bookingRef": "HOTEL77",
      "sourceEmail": "...", "priorityScore": 88, "confidence": 0.9, "tripType": "hotel"
    }
  ],
  "conflicts": [
    {
      "conflictId": "conf_...", "eventId": "...", "otherEventId": "...",
      "type": "time_overlap", "detail": "...", "detectedAt": "..."
    }
  ]
}
```

Parsing is lenient on purpose. `TimelinePayloadParser` decodes each event and conflict
separately and drops the ones that don't decode (the counts are returned in
`TimelinePayloadParseResult`), so one bad record from the backend doesn't blank the whole
timeline. It only throws when the body isn't a JSON object or when `events`/`conflicts`
isn't an array.

`RemoteTimelineService` retries on 429/5xx responses and on transient `URLError`s
(timeout, lost connection, host unreachable), with exponential backoff starting at
0.35 s. Other 4xx responses fail immediately.
