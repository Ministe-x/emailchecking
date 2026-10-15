import Foundation

@MainActor
public final class TimelineViewModel: ObservableObject {
    @Published public private(set) var sections: [TimelineDaySection] = []
    @Published public private(set) var syncSnapshot: SyncSnapshot = .init()
    @Published public private(set) var errorMessage: String?
    @Published public var selectedAccountEmail: String
    @Published public var fetchLimit: Int

    private let timelineService: TimelineService
    private let correctionStore: CorrectionStore
    private var latestPayload: TimelinePayload?

    public init(
        timelineService: TimelineService,
        correctionStore: CorrectionStore,
        selectedAccountEmail: String = "demo.user@gmail.com",
        fetchLimit: Int = 30
    ) {
        self.timelineService = timelineService
        self.correctionStore = correctionStore
        self.selectedAccountEmail = selectedAccountEmail
        self.fetchLimit = fetchLimit
    }

    public func loadTimeline() async {
        syncSnapshot.isSyncing = true
        syncSnapshot.note = "Fetching timeline events"
        errorMessage = nil
        do {
            let payload = try await timelineService.fetchTimeline(
                accountEmail: selectedAccountEmail,
                limit: fetchLimit
            )
            latestPayload = payload
            rebuildSections(with: payload)
            syncSnapshot = SyncSnapshot(
                lastSyncAt: Date(),
                processedEvents: payload.events.count,
                totalEvents: payload.events.count,
                isSyncing: false,
                note: "Timeline updated"
            )
        } catch {
            syncSnapshot.isSyncing = false
            syncSnapshot.note = "Sync failed"
            errorMessage = error.localizedDescription
        }
    }

    public func correction(for eventId: String) -> LocalCorrection? {
        correctionStore.loadAll()[eventId]
    }

    public func confirm(eventId: String) {
        let correction = LocalCorrection(eventId: eventId, decision: .confirmed)
        correctionStore.save(correction)
        refreshFromLatestPayload()
    }

    public func ignore(eventId: String) {
        let correction = LocalCorrection(eventId: eventId, decision: .ignored)
        correctionStore.save(correction)
        refreshFromLatestPayload()
    }

    public func edit(
        eventId: String,
        title: String?,
        location: String?,
        start: Date?,
        end: Date?
    ) {
        let correction = LocalCorrection(
            eventId: eventId,
            decision: .edited,
            editedTitle: title,
            editedLocation: location,
            editedStart: start,
            editedEnd: end
        )
        correctionStore.save(correction)
        refreshFromLatestPayload()
    }

    public func resetCorrection(eventId: String) {
        correctionStore.remove(eventId: eventId)
        refreshFromLatestPayload()
    }

    private func refreshFromLatestPayload() {
        if let latestPayload {
            rebuildSections(with: latestPayload)
        }
    }

    private func rebuildSections(with payload: TimelinePayload) {
        let corrections = correctionStore.loadAll()
        let conflictMap = Dictionary(grouping: payload.conflicts, by: \.eventId)
        let calendar = Calendar.current
        let grouped = Dictionary(grouping: payload.events) { event -> Date in
            let day = event.startDate ?? Date()
            return calendar.startOfDay(for: day)
        }

        let sortedDays = grouped.keys.sorted()
        let builtSections = sortedDays.map { day -> TimelineDaySection in
            let dayEvents = (grouped[day] ?? [])
                .sorted {
                    ($0.startDate ?? .distantFuture) < ($1.startDate ?? .distantFuture)
                }
                .map { event in
                    TripDisplayEvent(
                        event: event,
                        correction: corrections[event.eventId],
                        conflictBadges: (conflictMap[event.eventId] ?? []).map(\.type)
                    )
                }
            return TimelineDaySection(day: day, events: dayEvents)
        }

        sections = builtSections
    }
}
