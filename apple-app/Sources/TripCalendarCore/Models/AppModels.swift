import Foundation

public enum MailboxProvider: String, Codable, CaseIterable, Identifiable {
    case gmail
    case school

    public var id: String { rawValue }

    public var displayName: String {
        switch self {
        case .gmail:
            return "Gmail"
        case .school:
            return "School Mailbox"
        }
    }
}

public enum ConnectionState: String, Codable {
    case disconnected
    case connected
    case syncing
    case error
}

public struct MailboxConnectionStatus: Codable, Equatable, Identifiable {
    public let provider: MailboxProvider
    public var state: ConnectionState
    public var accountHint: String?
    public var message: String?

    public var id: String { provider.id }

    public init(provider: MailboxProvider, state: ConnectionState, accountHint: String?, message: String?) {
        self.provider = provider
        self.state = state
        self.accountHint = accountHint
        self.message = message
    }
}

public struct SyncSnapshot: Equatable {
    public var lastSyncAt: Date?
    public var processedEvents: Int
    public var totalEvents: Int
    public var isSyncing: Bool
    public var note: String?

    public init(
        lastSyncAt: Date? = nil,
        processedEvents: Int = 0,
        totalEvents: Int = 0,
        isSyncing: Bool = false,
        note: String? = nil
    ) {
        self.lastSyncAt = lastSyncAt
        self.processedEvents = processedEvents
        self.totalEvents = totalEvents
        self.isSyncing = isSyncing
        self.note = note
    }
}

public enum CorrectionDecision: String, Codable {
    case confirmed
    case ignored
    case edited
}

public struct LocalCorrection: Codable, Equatable {
    public let eventId: String
    public var decision: CorrectionDecision
    public var editedTitle: String?
    public var editedLocation: String?
    public var editedStart: Date?
    public var editedEnd: Date?
    public var aiReasonOverride: String?
    public var updatedAt: Date

    public init(
        eventId: String,
        decision: CorrectionDecision,
        editedTitle: String? = nil,
        editedLocation: String? = nil,
        editedStart: Date? = nil,
        editedEnd: Date? = nil,
        aiReasonOverride: String? = nil,
        updatedAt: Date = Date()
    ) {
        self.eventId = eventId
        self.decision = decision
        self.editedTitle = editedTitle
        self.editedLocation = editedLocation
        self.editedStart = editedStart
        self.editedEnd = editedEnd
        self.aiReasonOverride = aiReasonOverride
        self.updatedAt = updatedAt
    }
}
