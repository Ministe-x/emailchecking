import Foundation
import XCTest
@testable import TripCalendarCore

@MainActor
final class TimelineViewModelTests: XCTestCase {
    func testLoadTimelineBuildsSectionsAndConflictBadges() async {
        let payload = TimelinePayload(
            events: [
                TripEvent(
                    eventId: "evt-1",
                    title: "Flight",
                    start: "2026-10-10T10:00:00+00:00",
                    end: "2026-10-10T12:00:00+00:00",
                    timezone: "UTC",
                    location: "LHR",
                    bookingRef: "AA",
                    sourceEmail: "a@example.com",
                    priorityScore: 90,
                    confidence: 0.9,
                    tripType: "flight"
                ),
                TripEvent(
                    eventId: "evt-2",
                    title: "Hotel",
                    start: "2026-10-11T10:00:00+00:00",
                    end: "2026-10-11T12:00:00+00:00",
                    timezone: "UTC",
                    location: "Hilton",
                    bookingRef: nil,
                    sourceEmail: "b@example.com",
                    priorityScore: 70,
                    confidence: 0.8,
                    tripType: "hotel"
                ),
            ],
            conflicts: [
                EventConflict(
                    conflictId: "conf-1",
                    eventId: "evt-1",
                    otherEventId: "evt-2",
                    type: "overlap",
                    detail: "Overlap",
                    detectedAt: "2026-10-09T10:00:00+00:00"
                ),
            ]
        )
        let service = StubTimelineService(payload: payload)
        let store = InMemoryCorrectionStore()
        let viewModel = TimelineViewModel(
            timelineService: service,
            correctionStore: store
        )

        await viewModel.loadTimeline()

        XCTAssertEqual(viewModel.sections.count, 2)
        XCTAssertEqual(viewModel.sections.first?.events.first?.conflictBadges, ["overlap"])
        XCTAssertEqual(viewModel.syncSnapshot.totalEvents, 2)
    }

    func testCorrectionFlowsPersistAndRefreshEventPresentation() async {
        let payload = TimelinePayload(
            events: [
                TripEvent(
                    eventId: "evt-1",
                    title: "Original Flight",
                    start: "2026-10-10T10:00:00+00:00",
                    end: "2026-10-10T12:00:00+00:00",
                    timezone: "UTC",
                    location: "LHR",
                    bookingRef: nil,
                    sourceEmail: "a@example.com",
                    priorityScore: 90,
                    confidence: 0.9,
                    tripType: "flight"
                ),
            ],
            conflicts: []
        )
        let service = StubTimelineService(payload: payload)
        let store = InMemoryCorrectionStore()
        let viewModel = TimelineViewModel(timelineService: service, correctionStore: store)
        await viewModel.loadTimeline()

        viewModel.confirm(eventId: "evt-1")
        XCTAssertEqual(store.loadAll()["evt-1"]?.decision, .confirmed)

        viewModel.edit(
            eventId: "evt-1",
            title: "Edited Flight",
            location: "SFO",
            start: nil,
            end: nil
        )
        XCTAssertEqual(viewModel.sections[0].events[0].effectiveTitle, "Edited Flight")
        XCTAssertEqual(viewModel.sections[0].events[0].effectiveLocation, "SFO")

        viewModel.resetCorrection(eventId: "evt-1")
        XCTAssertNil(store.loadAll()["evt-1"])
        XCTAssertEqual(viewModel.sections[0].events[0].effectiveTitle, "Original Flight")
    }

    func testLoadTimelineFailureSetsErrorState() async {
        let service = FailingTimelineService()
        let store = InMemoryCorrectionStore()
        let viewModel = TimelineViewModel(timelineService: service, correctionStore: store)

        await viewModel.loadTimeline()

        XCTAssertEqual(viewModel.syncSnapshot.note, "Sync failed")
        XCTAssertNotNil(viewModel.errorMessage)
    }
}

private struct StubTimelineService: TimelineService {
    let payload: TimelinePayload

    func fetchTimeline(accountEmail: String, limit: Int) async throws -> TimelinePayload {
        payload
    }
}

private struct FailingTimelineService: TimelineService {
    func fetchTimeline(accountEmail: String, limit: Int) async throws -> TimelinePayload {
        throw TimelineServiceError.transportError(message: "offline")
    }
}

private final class InMemoryCorrectionStore: CorrectionStore {
    private var storage: [String: LocalCorrection] = [:]

    func loadAll() -> [String: LocalCorrection] {
        storage
    }

    func save(_ correction: LocalCorrection) {
        storage[correction.eventId] = correction
    }

    func remove(eventId: String) {
        storage.removeValue(forKey: eventId)
    }
}
