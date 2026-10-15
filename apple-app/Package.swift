// swift-tools-version: 5.10
import PackageDescription

let package = Package(
    name: "TripCalendarAppleApp",
    defaultLocalization: "en",
    platforms: [
        .iOS(.v17),
        .macOS(.v14),
    ],
    products: [
        .library(
            name: "TripCalendarCore",
            targets: ["TripCalendarCore"]
        ),
        .executable(
            name: "TripCalendarApp",
            targets: ["TripCalendarApp"]
        ),
    ],
    targets: [
        .target(
            name: "TripCalendarCore"
        ),
        .executableTarget(
            name: "TripCalendarApp",
            dependencies: ["TripCalendarCore"]
        ),
        .testTarget(
            name: "TripCalendarCoreTests",
            dependencies: ["TripCalendarCore"]
        ),
    ]
)
