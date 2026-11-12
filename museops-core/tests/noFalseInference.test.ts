import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import * as api from "../index.js";
import { createFindings, createPulse, CrossSubjectError } from "../index.js";
import { runCreatorPipeline, testContext } from "./helpers.js";

const FORBIDDEN = /collaborat|relationship/i;

describe("no false inference", () => {
  it("produces two distinct Observations/Findings for two independent signals", () => {
    const ctx = testContext();
    const a = runCreatorPipeline("stephanie-live", { handle: "stephanie" }, ctx);
    const b = runCreatorPipeline("easyboy-update", { handle: "easyboy" }, ctx);

    expect(a.observations).toHaveLength(1);
    expect(b.observations).toHaveLength(1);
    expect(a.observations[0]!.subject_candidate).toBe("Stephanie");
    expect(b.observations[0]!.subject_candidate).toBe("EASYBOY");
    expect(a.subject.id).not.toBe(b.subject.id);

    const fa = createFindings(a.pulse, a.store, ctx);
    const fb = createFindings(b.pulse, b.store, ctx);
    expect(fa).toHaveLength(1);
    expect(fb).toHaveLength(1);
    expect(fa[0]!.id).not.toBe(fb[0]!.id);
    expect(fa[0]!.claim).toEqual({ type: "creator_event", value: { event_type: "live_started" } });
    expect(fb[0]!.claim).toEqual({ type: "creator_event", value: { event_type: "posted_update" } });

    const everything = JSON.stringify({ a: a.observations, b: b.observations, fa, fb, pa: a.pulse, pb: b.pulse });
    expect(everything).not.toMatch(FORBIDDEN);
  });

  it("refuses to aggregate two subjects into one Pulse", () => {
    const ctx = testContext();
    const a = runCreatorPipeline("stephanie-live", { handle: "stephanie" }, ctx);
    const b = runCreatorPipeline("easyboy-update", { handle: "easyboy" }, ctx);
    expect(() => createPulse([...a.sets, ...b.sets], ctx)).toThrow(CrossSubjectError);
  });

  it("does not turn unrelated claims about one subject into a single claim", () => {
    const ctx = testContext();
    const a = runCreatorPipeline("stephanie-live", { handle: "stephanie" }, ctx);
    const extra = { ...a.observations[0]!, id: "obs_x", claim: { type: "creator_event", value: { event_type: "posted_update" } } };
    const store = { ...a.store, observations: [...a.store.observations, extra], observationSets: [{ ...a.sets[0]!, observation_ids: [...a.sets[0]!.observation_ids, "obs_x"] }] };
    const findings = createFindings(a.pulse, store, ctx);
    expect(findings).toHaveLength(2);
  });

  it("exposes no relationship/collaboration capability in the public API", () => {
    expect(Object.keys(api).filter((k) => FORBIDDEN.test(k))).toEqual([]);
  });

  it("contains no relationship/collaboration code path in the package source", () => {
    const root = fileURLToPath(new URL("..", import.meta.url));
    const files: string[] = [];
    for (const dir of ["domain", "application", "capabilities"]) {
      const walk = (d: string): void => {
        for (const name of readdirSync(d)) {
          const p = join(d, name);
          if (statSync(p).isDirectory()) walk(p);
          else if (p.endsWith(".ts")) files.push(p);
        }
      };
      walk(join(root, dir));
    }
    expect(files.length).toBeGreaterThan(10);
    const offenders = files.filter((f) => FORBIDDEN.test(readFileSync(f, "utf8")));
    expect(offenders).toEqual([]);
  });
});
