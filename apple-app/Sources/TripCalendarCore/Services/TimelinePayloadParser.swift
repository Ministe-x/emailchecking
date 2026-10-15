import Foundation

public enum TimelinePayloadParseError: Error, LocalizedError {
    case invalidJSON
    case invalidRootObject

    public var errorDescription: String? {
        switch self {
        case .invalidJSON:
            return "Timeline payload is not valid JSON."
        case .invalidRootObject:
            return "Timeline payload root object is malformed."
        }
    }
}

public struct TimelinePayloadParseResult: Equatable {
    public let payload: TimelinePayload
    public let droppedEvents: Int
    public let droppedConflicts: Int

    public init(payload: TimelinePayload, droppedEvents: Int, droppedConflicts: Int) {
        self.payload = payload
        self.droppedEvents = droppedEvents
        self.droppedConflicts = droppedConflicts
    }
}

public enum TimelinePayloadParser {
    public static func parse(_ data: Data) throws -> TimelinePayload {
        try parseWithDiagnostics(data).payload
    }

    public static func parseWithDiagnostics(_ data: Data) throws -> TimelinePayloadParseResult {
        let rawObject = try JSONSerialization.jsonObject(with: data)
        guard let root = rawObject as? [String: Any] else {
            throw TimelinePayloadParseError.invalidRootObject
        }
        let eventValues = try parseArrayField(name: "events", root: root)
        let conflictValues = try parseArrayField(name: "conflicts", root: root)

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        var parsedEvents: [TripEvent] = []
        var parsedConflicts: [EventConflict] = []

        for value in eventValues {
            if let event = try? decodeItem(value, as: TripEvent.self, decoder: decoder) {
                parsedEvents.append(event)
            }
        }
        for value in conflictValues {
            if let conflict = try? decodeItem(value, as: EventConflict.self, decoder: decoder) {
                parsedConflicts.append(conflict)
            }
        }
        return TimelinePayloadParseResult(
            payload: TimelinePayload(events: parsedEvents, conflicts: parsedConflicts),
            droppedEvents: eventValues.count - parsedEvents.count,
            droppedConflicts: conflictValues.count - parsedConflicts.count
        )
    }

    private static func decodeItem<T: Decodable>(
        _ value: Any,
        as type: T.Type,
        decoder: JSONDecoder
    ) throws -> T {
        guard JSONSerialization.isValidJSONObject(value) else {
            throw TimelinePayloadParseError.invalidJSON
        }
        let itemData = try JSONSerialization.data(withJSONObject: value)
        return try decoder.decode(T.self, from: itemData)
    }

    private static func parseArrayField(name: String, root: [String: Any]) throws -> [Any] {
        guard let value = root[name] else {
            return []
        }
        guard let arrayValue = value as? [Any] else {
            throw TimelinePayloadParseError.invalidRootObject
        }
        return arrayValue
    }
}
