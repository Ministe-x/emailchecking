import SwiftUI
import TripCalendarCore

struct RootView: View {
    @ObservedObject var accountViewModel: AccountStatusViewModel
    @ObservedObject var syncViewModel: SyncStatusViewModel
    @ObservedObject var timelineViewModel: TimelineViewModel

    var body: some View {
        TabView {
            AccountStatusView(viewModel: accountViewModel)
                .tabItem {
                    Label("Accounts", systemImage: "person.crop.circle")
                }

            SyncStatusView(viewModel: syncViewModel)
                .tabItem {
                    Label("Sync", systemImage: "arrow.triangle.2.circlepath")
                }

            TimelineView(viewModel: timelineViewModel)
                .tabItem {
                    Label("Timeline", systemImage: "calendar")
                }
        }
    }
}
