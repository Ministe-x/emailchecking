import Combine
import Foundation

@MainActor
public final class SyncStatusViewModel: ObservableObject {
    @Published public private(set) var snapshot: SyncSnapshot = .init(note: "Waiting for first sync")

    private var cancellables: Set<AnyCancellable> = []

    public init() {}

    public func bind(to timelineViewModel: TimelineViewModel) {
        timelineViewModel.$syncSnapshot
            .receive(on: RunLoop.main)
            .sink { [weak self] in
                self?.snapshot = $0
            }
            .store(in: &cancellables)
    }
}
