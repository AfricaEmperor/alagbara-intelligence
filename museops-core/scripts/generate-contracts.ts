/**
 * Generates versioned JSON Schema artifacts from the Zod schemas (the source of truth).
 *   tsx scripts/generate-contracts.ts          write contracts/v<major.minor>/
 *   tsx scripts/generate-contracts.ts --check  fail if committed artifacts differ
 * Only this script performs file I/O; the library itself performs none.
 */
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { z } from "zod";
import { MUSEOPS_CONTRACT_VERSION } from "../index.js";
import { ExternalIdentitySchema } from "../domain/externalIdentity.js";
import { FindingSchema } from "../domain/finding.js";
import { ObservationSchema } from "../domain/observation.js";
import { ObservationSetSchema } from "../domain/observationSet.js";
import { ProvenanceChainSchema } from "../domain/provenance.js";
import { PulseSchema } from "../domain/pulse.js";
import { SignalSchema } from "../domain/signal.js";
import { SourceSchema, SourceTypeDefinitionSchema } from "../domain/source.js";
import { SubjectSchema } from "../domain/subject.js";
import { RawInputSchema } from "../application/ingestSignal.js";

const SCHEMAS: ReadonlyArray<readonly [string, string, z.ZodType]> = [
  ["raw-input", "RawInput", RawInputSchema],
  ["source-type", "SourceTypeDefinition", SourceTypeDefinitionSchema],
  ["source", "Source", SourceSchema],
  ["signal", "Signal", SignalSchema],
  ["observation", "Observation", ObservationSchema],
  ["subject", "Subject", SubjectSchema],
  ["external-identity", "ExternalIdentity", ExternalIdentitySchema],
  ["observation-set", "ObservationSet", ObservationSetSchema],
  ["pulse", "Pulse", PulseSchema],
  ["finding", "Finding", FindingSchema],
  ["provenance-chain", "ProvenanceChain", ProvenanceChainSchema],
];

const [major = "0", minor = "0"] = MUSEOPS_CONTRACT_VERSION.split(".");
const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const outDir = join(root, "contracts", `v${major}.${minor}`);

function build(): Map<string, string> {
  const files = new Map<string, string>();
  const manifest: Array<{ name: string; file: string; sha256: string }> = [];
  for (const [file, title, schema] of SCHEMAS) {
    const json = z.toJSONSchema(schema, { target: "draft-2020-12" }) as Record<string, unknown>;
    const doc = {
      ...json,
      $id: `urn:alagbara:museops:contract:${MUSEOPS_CONTRACT_VERSION}:${file}`,
      title: `MuseOps ${title}`,
    };
    const text = JSON.stringify(doc, null, 2) + "\n";
    files.set(`${file}.schema.json`, text);
    manifest.push({ name: title, file: `${file}.schema.json`, sha256: createHash("sha256").update(text).digest("hex") });
  }
  files.set(
    "manifest.json",
    JSON.stringify({ contract: "museops-core", contract_version: MUSEOPS_CONTRACT_VERSION, schemas: manifest }, null, 2) + "\n",
  );
  return files;
}

const generated = build();
if (process.argv.includes("--check")) {
  const problems: string[] = [];
  for (const [name, text] of generated) {
    const path = join(outDir, name);
    if (!existsSync(path)) problems.push(`missing: ${name}`);
    else if (readFileSync(path, "utf8") !== text) problems.push(`stale: ${name}`);
  }
  if (problems.length > 0) {
    console.error(`Contract artifacts out of date (run "npm run contracts:generate"):\n  ${problems.join("\n  ")}`);
    process.exit(1);
  }
  console.log(`Contracts consistent: ${generated.size} files in contracts/v${major}.${minor}`);
} else {
  mkdirSync(outDir, { recursive: true });
  for (const [name, text] of generated) writeFileSync(join(outDir, name), text);
  console.log(`Wrote ${generated.size} files to contracts/v${major}.${minor}`);
}
