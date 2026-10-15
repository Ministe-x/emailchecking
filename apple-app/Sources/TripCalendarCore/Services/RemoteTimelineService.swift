import Foundation

public enum TimelineServiceError: Error, LocalizedError {
    case invalidURL
    case invalidResponse
    case transportError(message: String)
    case malformedPayload(message: String)
    case requestFailed(statusCode: Int, body: String)

    public var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "The timeline endpoint URL is invalid."
        case .invalidResponse:
            return "The timeline endpoint returned an unexpected response."
        case .transportError(let message):
            return "Timeline request failed due to a network error: \(message)"
        case .malformedPayload(let message):
            return "Timeline payload is malformed: \(message)"
        case .requestFailed(let statusCode, let body):
            return "Timeline request failed (\(statusCode)): \(body)"
        }
    }
}

public struct TimelineRequestRetryPolicy: Equatable {
    public let maxAttempts: Int
    public let baseDelaySeconds: TimeInterval
    public let backoffMultiplier: Double
    public let retriableStatusCodes: Set<Int>

    public init(
        maxAttempts: Int = 3,
        baseDelaySeconds: TimeInterval = 0.35,
        backoffMultiplier: Double = 2.0,
        retriableStatusCodes: Set<Int> = [429, 500, 502, 503, 504]
    ) {
        self.maxAttempts = max(1, maxAttempts)
        self.baseDelaySeconds = max(0, baseDelaySeconds)
        self.backoffMultiplier = max(1, backoffMultiplier)
        self.retriableStatusCodes = retriableStatusCodes
    }
}

public struct TimelineNetworkConfiguration: Equatable {
    public let timeoutInterval: TimeInterval
    public let retryPolicy: TimelineRequestRetryPolicy

    public init(timeoutInterval: TimeInterval = 10, retryPolicy: TimelineRequestRetryPolicy = .init()) {
        self.timeoutInterval = max(1, timeoutInterval)
        self.retryPolicy = retryPolicy
    }
}

public final class RemoteTimelineService: TimelineService {
    private let configuration: TimelineEndpointConfiguration
    private let session: URLSession
    private let networkConfiguration: TimelineNetworkConfiguration
    private let sleep: @Sendable (UInt64) async -> Void

    public init(
        configuration: TimelineEndpointConfiguration,
        session: URLSession = .shared,
        networkConfiguration: TimelineNetworkConfiguration = .init(),
        sleep: @escaping @Sendable (UInt64) async -> Void = { duration in
            try? await Task.sleep(nanoseconds: duration)
        }
    ) {
        self.configuration = configuration
        self.session = session
        self.networkConfiguration = networkConfiguration
        self.sleep = sleep
    }

    public func fetchTimeline(accountEmail: String, limit: Int) async throws -> TimelinePayload {
        guard var components = URLComponents(
            url: configuration.baseURL.appending(path: configuration.path),
            resolvingAgainstBaseURL: false
        ) else {
            throw TimelineServiceError.invalidURL
        }

        components.queryItems = [
            URLQueryItem(name: "accountEmail", value: accountEmail),
            URLQueryItem(name: "limit", value: String(limit)),
        ]
        guard let url = components.url else {
            throw TimelineServiceError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.timeoutInterval = networkConfiguration.timeoutInterval

        let retry = networkConfiguration.retryPolicy
        for attempt in 1 ... retry.maxAttempts {
            do {
                let (data, response) = try await session.data(for: request)
                guard let httpResponse = response as? HTTPURLResponse else {
                    throw TimelineServiceError.invalidResponse
                }
                if !(200 ..< 300).contains(httpResponse.statusCode) {
                    if retry.retriableStatusCodes.contains(httpResponse.statusCode), attempt < retry.maxAttempts {
                        await sleep(backoffNanoseconds(attempt: attempt))
                        continue
                    }
                    throw TimelineServiceError.requestFailed(
                        statusCode: httpResponse.statusCode,
                        body: String(data: data, encoding: .utf8) ?? "No response body"
                    )
                }

                do {
                    let parsed = try TimelinePayloadParser.parseWithDiagnostics(data)
                    return parsed.payload
                } catch {
                    throw TimelineServiceError.malformedPayload(message: error.localizedDescription)
                }
            } catch {
                if shouldRetry(error: error), attempt < retry.maxAttempts {
                    await sleep(backoffNanoseconds(attempt: attempt))
                    continue
                }
                if let timelineError = error as? TimelineServiceError {
                    throw timelineError
                }
                throw TimelineServiceError.transportError(message: error.localizedDescription)
            }
        }
        throw TimelineServiceError.transportError(message: "Exhausted retry attempts")
    }

    private func shouldRetry(error: Error) -> Bool {
        guard let urlError = error as? URLError else {
            return false
        }
        switch urlError.code {
        case .timedOut, .cannotFindHost, .cannotConnectToHost, .networkConnectionLost, .notConnectedToInternet:
            return true
        default:
            return false
        }
    }

    private func backoffNanoseconds(attempt: Int) -> UInt64 {
        let retry = networkConfiguration.retryPolicy
        let exponent = Double(max(0, attempt - 1))
        let seconds = retry.baseDelaySeconds * pow(retry.backoffMultiplier, exponent)
        return UInt64(max(0, seconds) * 1_000_000_000)
    }
}
