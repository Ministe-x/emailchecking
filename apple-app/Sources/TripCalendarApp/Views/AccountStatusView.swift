import SwiftUI
import TripCalendarCore

struct AccountStatusView: View {
    @ObservedObject var viewModel: AccountStatusViewModel

    var body: some View {
        NavigationStack {
            List(viewModel.statuses) { status in
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Text(status.provider.displayName)
                            .font(.headline)
                        Spacer()
                        StatePill(state: status.state)
                    }
                    if let accountHint = status.accountHint {
                        Text(accountHint)
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                    if let message = status.message {
                        Text(message)
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                }
                .padding(.vertical, 4)
            }
            .navigationTitle("Mailbox Connections")
        }
    }
}

private struct StatePill: View {
    let state: ConnectionState

    var body: some View {
        Text(state.rawValue.capitalized)
            .font(.caption.weight(.semibold))
            .padding(.horizontal, 10)
            .padding(.vertical, 4)
            .background(backgroundColor.opacity(0.18))
            .foregroundStyle(backgroundColor)
            .clipShape(Capsule())
    }

    private var backgroundColor: Color {
        switch state {
        case .connected:
            return .green
        case .syncing:
            return .blue
        case .disconnected:
            return .orange
        case .error:
            return .red
        }
    }
}
