import Foundation

public struct TimelinePayload: Codable, Equatable {
    public let events: [TripEvent]
    public let conflicts: [EventConflict]

    public init(events: [TripEvent], conflicts: [EventConflict]) {
        self.events = events
        self.conflicts = conflicts
    }
}

public struct TripEvent: Codable, Equatable, Identifiable {
    public let eventId: String
    public let title: String
    public let start: String
    public let end: String
    public let timezone: String
    public let location: String?
    public let bookingRef: String?
    public let sourceEmail: String
    public let priorityScore: Int
    public let confidence: Double
    public let tripType: String

    public var id: String { eventId }

    public var startDate: Date? {
        TimelineDateParser.parse(start)
    }

    public var endDate: Date? {
        TimelineDateParser.parse(end)
    }
}

public struct EventConflict: Codable, Equatable, Identifiable {
    public let conflictId: String
    public let eventId: String
    public let otherEventId: String
    public let type: String
    public let detail: String
    public let detectedAt: String

    public var id: String { conflictId }
}

public struct TimelineDaySection: Equatable {
    public let day: Date
    public let events: [TripDisplayEvent]

    public init(day: Date, events: [TripDisplayEvent]) {
        self.day = day
        self.events = events
    }
}

public struct TripDisplayEvent: Equatable, Identifiable {
    public let event: TripEvent
    public let correction: LocalCorrection?
    public let conflictBadges: [String]

    public var id: String { event.eventId }

    public var effectiveTitle: String {
        if let editedTitle = correction?.editedTitle, !editedTitle.isEmpty {
            return editedTitle
        }
        return event.title
    }

    public var effectiveLocation: String? {
        if let editedLocation = correction?.editedLocation {
            return editedLocation.isEmpty ? nil : editedLocation
        }
        return event.location
    }

    public var effectiveStart: Date? {
        correction?.editedStart ?? event.startDate
    }

    public var effectiveEnd: Date? {
        correction?.editedEnd ?? event.endDate
    }
}

enum TimelineDateParser {
    private static let formatters: [ISO8601DateFormatter] = {
        let basic = ISO8601DateFormatter()
        basic.formatOptions = [.withInternetDateTime]

        let withFractional = ISO8601DateFormatter()
        withFractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return [withFractional, basic]
    }()

    static func parse(_ value: String) -> Date? {
        for formatter in formatters {
            if let parsed = formatter.date(from: value) {
                return parsed
            }
        }
        return nil
    }
}
