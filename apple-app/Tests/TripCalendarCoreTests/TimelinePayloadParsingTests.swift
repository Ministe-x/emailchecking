import Foundation
import XCTest
@testable import TripCalendarCore

final class TimelinePayloadParsingTests: XCTestCase {
    func testParseTimelinePayloadContract() throws {
        let json = """
        {
          "events": [
            {
              "eventId": "evt-1",
              "title": "Flight to Tokyo",
              "start": "2026-10-10T10:00:00+00:00",
              "end": "2026-10-10T14:00:00+00:00",
              "timezone": "Asia/Tokyo",
              "location": "NRT",
              "bookingRef": "BOOK-123",
              "sourceEmail": "travel@example.com",
              "priorityScore": 91,
              "confidence": 0.95,
              "tripType": "flight"
            }
          ],
          "conflicts": [
            {
              "conflictId": "conf-1",
              "eventId": "evt-1",
              "otherEventId": "evt-2",
              "type": "overlap",
              "detail": "Overlaps with check-in",
              "detectedAt": "2026-10-09T12:00:00+00:00"
            }
          ]
        }
        """

        let payload = try TimelinePayloadParser.parse(Data(json.utf8))

        XCTAssertEqual(payload.events.count, 1)
        XCTAssertEqual(payload.conflicts.count, 1)
        XCTAssertEqual(payload.events[0].eventId, "evt-1")
        XCTAssertNotNil(payload.events[0].startDate)
        XCTAssertEqual(payload.conflicts[0].type, "overlap")
    }

    func testParseWithDiagnosticsDropsMalformedItems() throws {
        let json = """
        {
          "events": [
            {
              "eventId": "evt-1",
              "title": "Flight to Tokyo",
              "start": "2026-10-10T10:00:00+00:00",
              "end": "2026-10-10T14:00:00+00:00",
              "timezone": "Asia/Tokyo",
              "location": "NRT",
              "bookingRef": "BOOK-123",
              "sourceEmail": "travel@example.com",
              "priorityScore": 91,
              "confidence": 0.95,
              "tripType": "flight"
            },
            {
              "eventId": "evt-2",
              "title": "Broken event"
            }
          ],
          "conflicts": [
            {
              "conflictId": "conf-1",
              "eventId": "evt-1",
              "otherEventId": "evt-2",
              "type": "overlap",
              "detail": "Overlaps with check-in",
              "detectedAt": "2026-10-09T12:00:00+00:00"
            },
            {
              "conflictId": "conf-2"
            }
          ]
        }
        """

        let parsed = try TimelinePayloadParser.parseWithDiagnostics(Data(json.utf8))

        XCTAssertEqual(parsed.payload.events.count, 1)
        XCTAssertEqual(parsed.payload.conflicts.count, 1)
        XCTAssertEqual(parsed.droppedEvents, 1)
        XCTAssertEqual(parsed.droppedConflicts, 1)
    }
}
