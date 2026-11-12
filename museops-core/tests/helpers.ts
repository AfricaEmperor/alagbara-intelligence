import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import {
  createObservationSets, createPulse, createSequentialIdGenerator, emptyRegistry, extractCreatorObservations,
  ingestSignal, resolveCreator,
} from "../index.js";
import type { Context, EvidenceStore, Observation, Signal, Source } from "../index.js";

export const NOW = "2026-08-24T10:00:00Z";

export function testContext(): Context {
  return { now: () => NOW, newId: createSequentialIdGenerator() };
}

export function fixture(name: string): unknown {
  const url = new URL(`../fixtures/tiktok/${name}.json`, import.meta.url);
  return JSON.parse(readFileSync(fileURLToPath(url), "utf8"));
}

export const TIMEFRAME = { start: "2026-08-24T00:00:00Z", end: "2026-08-24T23:59:59Z" };

/** Run one fixture through ingest → extract → resolve → set → pulse. */
export function runCreatorPipeline(name: string, candidate: { handle?: string; account_id?: string }, ctx = testContext()) {
  const { source, signal } = ingestSignal(fixture(name), ctx);
  const observations = extractCreatorObservations(signal, ctx);
  const { subject } = resolveCreator(emptyRegistry(), candidate, ctx);
  const sets = createObservationSets(observations.map((observation) => ({ observation, subject_id: subject.id })), TIMEFRAME, ctx);
  const pulse = createPulse(sets, ctx);
  const store: EvidenceStore = { observationSets: sets, observations, signals: [signal], sources: [source] };
  return { ctx, source, signal, observations, subject, sets, pulse, store };
}

export type { Observation, Signal, Source };
