import SwiftUI
import TripCalendarCore

@main
struct TripCalendarApp: App {
    @StateObject private var accountViewModel = AccountStatusViewModel()
    @StateObject private var timelineViewModel: TimelineViewModel
    @StateObject private var syncViewModel = SyncStatusViewModel()

    init() {
        let service = TimelineServiceFactory.makeDefault()
        let correctionStore = UserDefaultsCorrectionStore()
        _timelineViewModel = StateObject(
            wrappedValue: TimelineViewModel(
                timelineService: service,
                correctionStore: correctionStore
            )
        )
    }

    var body: some Scene {
        WindowGroup {
            RootView(
                accountViewModel: accountViewModel,
                syncViewModel: syncViewModel,
                timelineViewModel: timelineViewModel
            )
            .task {
                syncViewModel.bind(to: timelineViewModel)
                await timelineViewModel.loadTimeline()
            }
        }
    }
}
