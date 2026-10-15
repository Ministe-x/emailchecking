import Foundation

@MainActor
public final class TripDetailViewModel: ObservableObject {
    @Published public var editableTitle: String
    @Published public var editableLocation: String
    @Published public var editableStart: Date
    @Published public var editableEnd: Date

    public let trip: TripDisplayEvent

    public init(trip: TripDisplayEvent) {
        self.trip = trip
        self.editableTitle = trip.effectiveTitle
        self.editableLocation = trip.effectiveLocation ?? ""
        self.editableStart = trip.effectiveStart ?? Date()
        self.editableEnd = trip.effectiveEnd ?? Date().addingTimeInterval(3600)
    }
}
