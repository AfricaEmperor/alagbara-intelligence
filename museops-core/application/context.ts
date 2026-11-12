export type IdGenerator = (prefix: string) => string;

export interface Context {
  /** Returns an ISO 8601 UTC timestamp. */
  now: () => string;
  newId: IdGenerator;
}

/** Deterministic ids (`prefix_1`, `prefix_2`, ...) for tests and fixtures. */
export function createSequentialIdGenerator(): IdGenerator {
  const counters = new Map<string, number>();
  return (prefix) => {
    const next = (counters.get(prefix) ?? 0) + 1;
    counters.set(prefix, next);
    return `${prefix}_${next}`;
  };
}

export function createDefaultContext(): Context {
  return {
    now: () => new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
    newId: (prefix) => `${prefix}_${globalThis.crypto.randomUUID()}`,
  };
}

export function deepFreeze<T>(value: T): T {
  if (value !== null && typeof value === "object" && !Object.isFrozen(value)) {
    Object.freeze(value);
    for (const key of Object.keys(value as object)) {
      deepFreeze((value as Record<string, unknown>)[key]);
    }
  }
  return value;
}
