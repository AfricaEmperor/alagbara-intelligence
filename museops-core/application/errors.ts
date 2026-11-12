/** Raised when a link in Finding → Pulse → ObservationSet → Observation → Signal → Source is missing or inconsistent. */
export class ProvenanceError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ProvenanceError";
  }
}

/** Raised when an operation would aggregate or relate more than one Subject. */
export class CrossSubjectError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "CrossSubjectError";
  }
}
