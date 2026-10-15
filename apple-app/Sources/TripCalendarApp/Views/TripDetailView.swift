import SwiftUI
import TripCalendarCore

struct TripDetailView: View {
    let trip: TripDisplayEvent
    let onConfirm: () -> Void
    let onIgnore: () -> Void
    let onReset: () -> Void
    let onSaveEdit: (_ title: String, _ location: String, _ start: Date, _ end: Date) -> Void

    @StateObject private var viewModel: TripDetailViewModel

    init(
        trip: TripDisplayEvent,
        onConfirm: @escaping () -> Void,
        onIgnore: @escaping () -> Void,
        onReset: @escaping () -> Void,
        onSaveEdit: @escaping (_ title: String, _ location: String, _ start: Date, _ end: Date) -> Void
    ) {
        self.trip = trip
        self.onConfirm = onConfirm
        self.onIgnore = onIgnore
        self.onReset = onReset
        self.onSaveEdit = onSaveEdit
        _viewModel = StateObject(wrappedValue: TripDetailViewModel(trip: trip))
    }

    var body: some View {
        Form {
            Section("Trip Facts") {
                LabeledContent("Title", value: trip.effectiveTitle)
                LabeledContent("Source Email", value: trip.event.sourceEmail)
                LabeledContent("Trip Type", value: trip.event.tripType.capitalized)
                LabeledContent("Importance", value: "\(trip.event.priorityScore)")
                LabeledContent("Confidence", value: "\(Int(trip.event.confidence * 100))%")
                LabeledContent("AI Reasons", value: aiReasonText)
                if !trip.conflictBadges.isEmpty {
                    LabeledContent("Conflicts", value: trip.conflictBadges.joined(separator: ", "))
                }
            }

            Section("Manual Correction") {
                TextField("Title", text: $viewModel.editableTitle)
                TextField("Location", text: $viewModel.editableLocation)
                DatePicker("Start", selection: $viewModel.editableStart)
                DatePicker("End", selection: $viewModel.editableEnd)

                Button("Save Edit") {
                    onSaveEdit(
                        viewModel.editableTitle,
                        viewModel.editableLocation,
                        viewModel.editableStart,
                        viewModel.editableEnd
                    )
                }
            }

            Section("Feedback") {
                Button("Confirm Trip") {
                    onConfirm()
                }
                .foregroundStyle(.green)

                Button("Ignore Trip") {
                    onIgnore()
                }
                .foregroundStyle(.red)

                Button("Reset Local Override") {
                    onReset()
                }
            }
        }
        .navigationTitle("Trip Detail")
    }

    private var aiReasonText: String {
        "Priority \(trip.event.priorityScore), confidence \(Int(trip.event.confidence * 100))%, type \(trip.event.tripType)"
    }
}
