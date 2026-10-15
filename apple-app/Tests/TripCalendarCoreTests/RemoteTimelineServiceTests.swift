import Foundation
import XCTest
@testable import TripCalendarCore

final class RemoteTimelineServiceTests: XCTestCase {
    override func setUp() {
        super.setUp()
        MockURLProtocol.requestHandler = nil
    }

    func testRetriesServerErrorsBeforeSuccess() async throws {
        let session = makeMockSession()
        var callCount = 0
        MockURLProtocol.requestHandler = { request in
            callCount += 1
            if callCount < 3 {
                return (
                    HTTPURLResponse(url: request.url!, statusCode: 503, httpVersion: nil, headerFields: nil)!,
                    Data("{\"error\":\"temporary\"}".utf8)
                )
            }
            return (
                HTTPURLResponse(url: request.url!, statusCode: 200, httpVersion: nil, headerFields: nil)!,
                validPayload()
            )
        }
        let service = RemoteTimelineService(
            configuration: TimelineEndpointConfiguration(baseURL: URL(string: "https://example.test")!),
            session: session,
            networkConfiguration: TimelineNetworkConfiguration(
                timeoutInterval: 3,
                retryPolicy: TimelineRequestRetryPolicy(maxAttempts: 3, baseDelaySeconds: 0)
            )
        )

        let payload = try await service.fetchTimeline(accountEmail: "user@example.com", limit: 20)

        XCTAssertEqual(callCount, 3)
        XCTAssertEqual(payload.events.count, 1)
    }

    func testMalformedPayloadThrowsServiceError() async {
        let session = makeMockSession()
        MockURLProtocol.requestHandler = { request in
            (
                HTTPURLResponse(url: request.url!, statusCode: 200, httpVersion: nil, headerFields: nil)!,
                Data("{\"events\":\"bad\",\"conflicts\":[]}".utf8)
            )
        }
        let service = RemoteTimelineService(
            configuration: TimelineEndpointConfiguration(baseURL: URL(string: "https://example.test")!),
            session: session
        )

        do {
            _ = try await service.fetchTimeline(accountEmail: "user@example.com", limit: 20)
            XCTFail("Expected malformed payload error")
        } catch let error as TimelineServiceError {
            switch error {
            case .malformedPayload:
                break
            default:
                XCTFail("Expected malformed payload error, got \(error)")
            }
        } catch {
            XCTFail("Expected TimelineServiceError, got \(error)")
        }
    }
}

private func makeMockSession() -> URLSession {
    let config = URLSessionConfiguration.ephemeral
    config.protocolClasses = [MockURLProtocol.self]
    return URLSession(configuration: config)
}

private func validPayload() -> Data {
    Data(
        """
        {
          "events": [
            {
              "eventId": "evt-1",
              "title": "Flight",
              "start": "2026-10-10T10:00:00+00:00",
              "end": "2026-10-10T12:00:00+00:00",
              "timezone": "UTC",
              "location": "LHR",
              "bookingRef": null,
              "sourceEmail": "a@example.com",
              "priorityScore": 90,
              "confidence": 0.9,
              "tripType": "flight"
            }
          ],
          "conflicts": []
        }
        """.utf8
    )
}

private final class MockURLProtocol: URLProtocol {
    static var requestHandler: ((URLRequest) throws -> (HTTPURLResponse, Data))?

    override class func canInit(with request: URLRequest) -> Bool {
        true
    }

    override class func canonicalRequest(for request: URLRequest) -> URLRequest {
        request
    }

    override func startLoading() {
        guard let handler = MockURLProtocol.requestHandler else {
            client?.urlProtocol(self, didFailWithError: URLError(.badServerResponse))
            return
        }
        do {
            let (response, data) = try handler(request)
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: data)
            client?.urlProtocolDidFinishLoading(self)
        } catch {
            client?.urlProtocol(self, didFailWithError: error)
        }
    }

    override func stopLoading() {}
}
