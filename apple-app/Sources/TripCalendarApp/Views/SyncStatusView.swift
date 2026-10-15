import SwiftUI
import TripCalendarCore

struct SyncStatusView: View {
    @ObservedObject var viewModel: SyncStatusViewModel

    var body: some View {
        NavigationStack {
            VStack(alignment: .leading, spacing: 16) {
                HStack {
                    Label(
                        viewModel.snapshot.isSyncing ? "Syncing" : "Idle",
                        systemImage: viewModel.snapshot.isSyncing ? "bolt.horizontal.circle.fill" : "checkmark.circle"
                    )
                    .font(.headline)
                    Spacer()
                }

                if let lastSync = viewModel.snapshot.lastSyncAt {
                    LabeledContent("Last Sync", value: lastSync.formatted(date: .abbreviated, time: .shortened))
                } else {
                    LabeledContent("Last Sync", value: "Not synced yet")
                }

                if viewModel.snapshot.isSyncing && viewModel.snapshot.totalEvents == 0 {
                    ProgressView()
                } else {
                    ProgressView(value: progressValue, total: 1)
                        .tint(.blue)
                }

                LabeledContent("Processed", value: "\(viewModel.snapshot.processedEvents)")
                LabeledContent("Total Events", value: "\(viewModel.snapshot.totalEvents)")

                if let note = viewModel.snapshot.note {
                    Text(note)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }

                Spacer()
            }
            .padding()
            .navigationTitle("Sync Status")
        }
    }

    private var progressValue: Double {
        guard viewModel.snapshot.totalEvents > 0 else {
            return 0
        }
        return min(1, Double(viewModel.snapshot.processedEvents) / Double(viewModel.snapshot.totalEvents))
    }
}
