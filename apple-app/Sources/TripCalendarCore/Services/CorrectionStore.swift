import Foundation

public protocol CorrectionStore {
    func loadAll() -> [String: LocalCorrection]
    func save(_ correction: LocalCorrection)
    func remove(eventId: String)
}

public final class UserDefaultsCorrectionStore: CorrectionStore {
    private let defaults: UserDefaults
    private let storageKey: String

    public init(defaults: UserDefaults = .standard, storageKey: String = "localCorrections.v1") {
        self.defaults = defaults
        self.storageKey = storageKey
    }

    public func loadAll() -> [String: LocalCorrection] {
        guard let data = defaults.data(forKey: storageKey) else {
            return [:]
        }
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        guard let decoded = try? decoder.decode([String: LocalCorrection].self, from: data) else {
            return [:]
        }
        return decoded
    }

    public func save(_ correction: LocalCorrection) {
        var existing = loadAll()
        existing[correction.eventId] = correction
        persist(existing)
    }

    public func remove(eventId: String) {
        var existing = loadAll()
        existing.removeValue(forKey: eventId)
        persist(existing)
    }

    private func persist(_ value: [String: LocalCorrection]) {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        guard let data = try? encoder.encode(value) else {
            return
        }
        defaults.set(data, forKey: storageKey)
    }
}
