import { z } from "zod";
import type { ExternalIdentity } from "../domain/externalIdentity.js";
import type { Subject } from "../domain/subject.js";
import type { Context } from "./context.js";

export interface IdentityRegistry {
  readonly subjects: readonly Subject[];
  readonly identities: readonly ExternalIdentity[];
}

export const emptyRegistry = (): IdentityRegistry => ({ subjects: [], identities: [] });

export const CreatorCandidateSchema = z
  .strictObject({
    account_id: z.string().min(1).optional(),
    handle: z.string().min(1).optional(),
  })
  .refine((c) => c.account_id !== undefined || c.handle !== undefined, {
    message: "A creator candidate needs an account_id or a handle; a display name alone is not an identifier.",
  });
export type CreatorCandidate = z.infer<typeof CreatorCandidateSchema>;

export interface Resolution {
  registry: IdentityRegistry;
  subject: Subject;
  created: boolean;
  /**
   * True when a presented identifier already belongs to a *different* Subject.
   * Subjects are never merged; the conflicting identifier is not re-assigned.
   */
  conflict: boolean;
}

/** normalized_hashtag = lowercase(remove("#")) (schema-freeze, Hashtag). */
export function normalizeHashtag(raw: string): string {
  const normalized = raw.replaceAll("#", "").toLowerCase();
  if (normalized.length === 0) throw new Error("Hashtag is empty after normalization");
  return normalized;
}

const PLATFORM = "tiktok" as const;

function find(reg: IdentityRegistry, type: ExternalIdentity["identifier_type"], value: string) {
  return reg.identities.find(
    (i) => i.platform === PLATFORM && i.identifier_type === type && i.value === value,
  );
}

function subjectOf(reg: IdentityRegistry, id: string): Subject {
  const subject = reg.subjects.find((s) => s.id === id);
  if (!subject) throw new Error(`Registry is inconsistent: missing subject ${id}`);
  return subject;
}

/**
 * Creator resolution: account_id exact match, then handle exact match.
 * No similarity matching, no rename detection, no automatic merging.
 */
export function resolveCreator(registry: IdentityRegistry, candidateInput: unknown, ctx: Context): Resolution {
  const candidate = CreatorCandidateSchema.parse(candidateInput);

  const byAccount = candidate.account_id ? find(registry, "account_id", candidate.account_id) : undefined;
  const byHandle = candidate.handle ? find(registry, "handle", candidate.handle) : undefined;
  const matched = byAccount ?? byHandle;

  if (matched) {
    const subject = subjectOf(registry, matched.subject_id);
    let conflict = false;
    const additions: ExternalIdentity[] = [];
    // Record a not-yet-known handle against the account_id-resolved subject,
    // unless that handle already belongs to a different subject.
    if (byAccount && candidate.handle) {
      if (byHandle && byHandle.subject_id !== subject.id) conflict = true;
      else if (!byHandle) {
        additions.push({
          id: ctx.newId("xid"),
          subject_id: subject.id,
          platform: PLATFORM,
          identifier_type: "handle",
          value: candidate.handle,
          identity_link_status: "observed",
        });
      }
    }
    // A presented account_id that is unknown, while the handle matched a subject: do not attach.
    if (!byAccount && candidate.account_id && byHandle) conflict = true;
    return {
      registry: { subjects: registry.subjects, identities: [...registry.identities, ...additions] },
      subject,
      created: false,
      conflict,
    };
  }

  const subject: Subject = {
    id: ctx.newId("sub"),
    type: "creator",
    status: "new",
    created_at: ctx.now(),
  };
  const identities: ExternalIdentity[] = [];
  if (candidate.account_id) {
    identities.push({
      id: ctx.newId("xid"), subject_id: subject.id, platform: PLATFORM,
      identifier_type: "account_id", value: candidate.account_id, identity_link_status: "observed",
    });
  }
  if (candidate.handle) {
    identities.push({
      id: ctx.newId("xid"), subject_id: subject.id, platform: PLATFORM,
      identifier_type: "handle", value: candidate.handle, identity_link_status: "observed",
    });
  }
  return {
    registry: { subjects: [...registry.subjects, subject], identities: [...registry.identities, ...identities] },
    subject,
    created: true,
    conflict: false,
  };
}

/** Hashtag resolution: exact match on the normalized value. */
export function resolveHashtag(registry: IdentityRegistry, raw: string, ctx: Context): Resolution {
  const normalized = normalizeHashtag(raw);
  const existing = find(registry, "normalized_hashtag", normalized);
  if (existing) {
    return { registry, subject: subjectOf(registry, existing.subject_id), created: false, conflict: false };
  }
  const subject: Subject = { id: ctx.newId("sub"), type: "hashtag", status: "new", created_at: ctx.now() };
  const identity: ExternalIdentity = {
    id: ctx.newId("xid"), subject_id: subject.id, platform: PLATFORM,
    identifier_type: "normalized_hashtag", value: normalized, identity_link_status: "observed",
  };
  return {
    registry: { subjects: [...registry.subjects, subject], identities: [...registry.identities, identity] },
    subject,
    created: true,
    conflict: false,
  };
}
