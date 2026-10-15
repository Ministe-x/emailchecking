import SwiftUI
import TripCalendarCore

struct TimelineView: View {
    @ObservedObject var viewModel: TimelineViewModel

    var body: some View {
        NavigationStack {
            List {
                if let errorMessage = viewModel.errorMessage {
                    Section {
                        Text(errorMessage)
                            .foregroundStyle(.red)
                            .font(.footnote)
                    }
                }

                ForEach(viewModel.sections, id: \.day) { section in
                    Section(section.day.formatted(date: .complete, time: .omitted)) {
                        ForEach(section.events) { trip in
                            NavigationLink {
                                TripDetailView(
                                    trip: trip,
                                    onConfirm: { viewModel.confirm(eventId: trip.id) },
                                    onIgnore: { viewModel.ignore(eventId: trip.id) },
                                    onReset: { viewModel.resetCorrection(eventId: trip.id) },
                                    onSaveEdit: { title, location, start, end in
                                        viewModel.edit(
                                            eventId: trip.id,
                                            title: title,
                                            location: location,
                                            start: start,
                                            end: end
                                        )
                                    }
                                )
                            } label: {
                                EventRow(trip: trip)
                            }
                        }
                    }
                }
            }
            .refreshable {
                await viewModel.loadTimeline()
            }
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button("Sync Now") {
                        Task {
                            await viewModel.loadTimeline()
                        }
                    }
                }
            }
            .navigationTitle("Trip Timeline")
        }
    }
}

private struct EventRow: View {
    let trip: TripDisplayEvent

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(trip.effectiveTitle)
                .font(.headline)
            HStack {
                Label(startLabel, systemImage: "clock")
                if let location = trip.effectiveLocation {
                    Label(location, systemImage: "mappin.and.ellipse")
                }
            }
            .font(.subheadline)
            .foregroundStyle(.secondary)

            HStack(spacing: 8) {
                Badge(text: "P\(trip.event.priorityScore)", color: .blue)
                Badge(text: "C\(Int(trip.event.confidence * 100))%", color: .purple)
                Badge(text: trip.event.tripType.capitalized, color: .mint)
                ForEach(trip.conflictBadges, id: \.self) { conflict in
                    Badge(text: conflict, color: .red)
                }
                if let correction = trip.correction {
                    Badge(text: correction.decision.rawValue.capitalized, color: .orange)
                }
            }
            .font(.caption)
        }
        .padding(.vertical, 4)
    }

    private var startLabel: String {
        guard let start = trip.effectiveStart else {
            return "Unknown time"
        }
        return start.formatted(date: .omitted, time: .shortened)
    }
}

private struct Badge: View {
    let text: String
    let color: Color

    var body: some View {
        Text(text)
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(color.opacity(0.16))
            .foregroundStyle(color)
            .clipShape(Capsule())
    }
}
