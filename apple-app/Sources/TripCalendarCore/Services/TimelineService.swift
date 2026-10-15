import Foundation

public protocol TimelineService {
    func fetchTimeline(accountEmail: String, limit: Int) async throws -> TimelinePayload
}

public struct TimelineEndpointConfiguration: Equatable {
    public let baseURL: URL
    public let path: String

    public init(baseURL: URL, path: String = "/calendar/timeline") {
        self.baseURL = baseURL
        self.path = path
    }
}

public enum TimelineServiceFactory {
    public static func makeDefault() -> TimelineService {
        if
            let baseURLRaw = ProcessInfo.processInfo.environment["TIMELINE_API_BASE_URL"],
            let baseURL = URL(string: baseURLRaw)
        {
            let path = ProcessInfo.processInfo.environment["TIMELINE_API_PATH"] ?? "/calendar/timeline"
            let timeout = Double(ProcessInfo.processInfo.environment["TIMELINE_API_TIMEOUT_SECONDS"] ?? "")
            let retries = Int(ProcessInfo.processInfo.environment["TIMELINE_API_MAX_RETRIES"] ?? "")
            return RemoteTimelineService(
                configuration: TimelineEndpointConfiguration(baseURL: baseURL, path: path),
                networkConfiguration: TimelineNetworkConfiguration(
                    timeoutInterval: timeout ?? 10,
                    retryPolicy: TimelineRequestRetryPolicy(maxAttempts: retries ?? 3)
                )
            )
        }
        return MockTimelineService()
    }
}
