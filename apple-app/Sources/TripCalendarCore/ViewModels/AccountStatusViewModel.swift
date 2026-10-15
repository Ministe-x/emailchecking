import Foundation

@MainActor
public final class AccountStatusViewModel: ObservableObject {
    @Published public private(set) var statuses: [MailboxConnectionStatus]

    public init(statuses: [MailboxConnectionStatus]? = nil) {
        self.statuses = statuses ?? Self.defaultStatuses()
    }

    public func setState(
        for provider: MailboxProvider,
        state: ConnectionState,
        accountHint: String? = nil,
        message: String? = nil
    ) {
        guard let index = statuses.firstIndex(where: { $0.provider == provider }) else {
            return
        }
        statuses[index].state = state
        statuses[index].accountHint = accountHint
        statuses[index].message = message
    }

    private static func defaultStatuses() -> [MailboxConnectionStatus] {
        [
            MailboxConnectionStatus(
                provider: .gmail,
                state: .connected,
                accountHint: "demo.user@gmail.com",
                message: "Connected for read-only trip extraction"
            ),
            MailboxConnectionStatus(
                provider: .school,
                state: .disconnected,
                accountHint: nil,
                message: "Connect your school mailbox to include campus trips"
            ),
        ]
    }
}
