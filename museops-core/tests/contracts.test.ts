import { execFileSync } from "node:child_process";
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { Ajv2020 } from "ajv/dist/2020.js";
import addFormatsModule from "ajv-formats";
import { describe, expect, it } from "vitest";
import { MUSEOPS_CONTRACT_VERSION } from "../index.js";
import { NOW } from "./helpers.js";

// ajv-formats ships CommonJS with a default export; unwrap it under NodeNext.
type FormatsPlugin = (ajv: Ajv2020) => unknown;
const addFormats = ((addFormatsModule as unknown as { default?: FormatsPlugin }).default ?? addFormatsModule) as unknown as FormatsPlugin;

const root = fileURLToPath(new URL("..", import.meta.url));
const dir = `${root}contracts/v0.1`;
const load = (n: string) => JSON.parse(readFileSync(`${dir}/${n}.schema.json`, "utf8")) as object;

function validator(name: string) {
  const ajv = new Ajv2020({ strict: false });
  addFormats(ajv);
  return ajv.compile(load(name));
}

describe("JSON Schema contracts", () => {
  it("committed artifacts are consistent with the Zod schemas (generator --check)", () => {
    const out = execFileSync(process.execPath, ["--import", "tsx", "scripts/generate-contracts.ts", "--check"], {
      cwd: root, encoding: "utf8",
    });
    expect(out).toContain("Contracts consistent");
  });

  it("manifest carries the package contract version and covers every schema file", () => {
    const manifest = JSON.parse(readFileSync(`${dir}/manifest.json`, "utf8")) as { contract_version: string; schemas: { file: string }[] };
    expect(manifest.contract_version).toBe(MUSEOPS_CONTRACT_VERSION);
    const files = readdirSync(dir).filter((f) => f.endsWith(".schema.json")).sort();
    expect(manifest.schemas.map((s) => s.file).sort()).toEqual(files);
  });

  it("Observation schema accepts numeric capability_confidence and rejects the legacy enum", () => {
    const check = validator("observation");
    const doc = {
      id: "obs_1", signal_id: "sig_1", claim: { type: "t", value: 1 },
      capability: "nlp", capability_confidence: 0.92, created_at: NOW,
    };
    expect(check(doc)).toBe(true);
    expect(check({ ...doc, capability_confidence: "high" })).toBe(false);
    expect(check({ ...doc, capability_confidence: 1.5 })).toBe(false);
    expect(check({ ...doc, evidence_strength: "medium" })).toBe(false);
  });

  it("Source-type schema permits an omitted default (api_response) and rejects a bogus default", () => {
    const check = validator("source-type");
    expect(check({ id: "api_response", type: "api_response" })).toBe(true);
    expect(check({ id: "screenshot", type: "screenshot", default_channel_trust: "medium" })).toBe(true);
    expect(check({ id: "x", type: "screenshot", default_channel_trust: "MEDIUM" })).toBe(false);
  });

  it("Finding schema requires pulse_id and forbids a generic confidence", () => {
    const check = validator("finding");
    const doc = {
      id: "f", pulse_id: "p", claim: { type: "t", value: 1 },
      evidence: { source_types: ["android_notification"], evidence_strength: "medium", contradictions: [] },
    };
    expect(check(doc)).toBe(true);
    const noPulse: Record<string, unknown> = { ...doc };
    delete noPulse.pulse_id;
    expect(check(noPulse)).toBe(false);
    expect(check({ ...doc, confidence: 0.9 })).toBe(false);
  });
});
