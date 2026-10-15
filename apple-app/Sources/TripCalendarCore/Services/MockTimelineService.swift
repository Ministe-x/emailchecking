import Foundation

public final class MockTimelineService: TimelineService {
    public init() {}

    public func fetchTimeline(accountEmail: String, limit: Int) async throws -> TimelinePayload {
        let now = Date()
        let startFormatter = ISO8601DateFormatter()
        startFormatter.formatOptions = [.withInternetDateTime]

        let events = [
            TripEvent(
                eventId: "evt-flight-001",
                title: "Flight to Berlin",
                start: startFormatter.string(from: now.addingTimeInterval(60 * 60 * 24)),
                end: startFormatter.string(from: now.addingTimeInterval(60 * 60 * 28)),
                timezone: "Europe/Berlin",
                location: "BER Airport",
                bookingRef: "AB12CD",
                sourceEmail: "booking@example-air.com",
                priorityScore: 94,
                confidence: 0.97,
                tripType: "flight"
            ),
            TripEvent(
                eventId: "evt-hotel-001",
                title: "Hotel Check-in",
                start: startFormatter.string(from: now.addingTimeInterval(60 * 60 * 29)),
                end: startFormatter.string(from: now.addingTimeInterval(60 * 60 * 52)),
                timezone: "Europe/Berlin",
                location: "Mitte Hotel",
                bookingRef: "HOTEL-7788",
                sourceEmail: "stay@hotel.com",
                priorityScore: 83,
                confidence: 0.88,
                tripType: "hotel"
            ),
        ]

        let conflicts = [
            EventConflict(
                conflictId: "conf-001",
                eventId: "evt-flight-001",
                otherEventId: "evt-hotel-001",
                type: "possible_overlap",
                detail: "Check-in is tight after estimated arrival.",
                detectedAt: startFormatter.string(from: now)
            ),
        ]

        return TimelinePayload(
            events: Array(events.prefix(max(0, limit))),
            conflicts: conflicts
        )
    }
}
