import { describe, expect, it } from "vitest";
import { emptyRegistry, normalizeHashtag, resolveCreator, resolveHashtag } from "../index.js";
import { testContext } from "./helpers.js";

describe("hashtag resolution", () => {
  it("resolves #Baddie and #baddie to exactly one Subject with value 'baddie'", () => {
    const ctx = testContext();
    const a = resolveHashtag(emptyRegistry(), "#Baddie", ctx);
    const b = resolveHashtag(a.registry, "#baddie", ctx);
    const c = resolveHashtag(b.registry, "#BADDIE", ctx);
    expect(a.created).toBe(true);
    expect(b.created).toBe(false);
    expect(c.subject.id).toBe(a.subject.id);
    expect(c.registry.subjects).toHaveLength(1);
    expect(c.registry.identities).toHaveLength(1);
    expect(c.registry.identities[0]).toMatchObject({
      identifier_type: "normalized_hashtag", value: "baddie", platform: "tiktok",
    });
  });

  it("normalizes with lowercase(remove('#')) and rejects empty results", () => {
    expect(normalizeHashtag("#Baddie")).toBe("baddie");
    expect(() => normalizeHashtag("#")).toThrow();
  });

  it("keeps different hashtags as different Subjects", () => {
    const ctx = testContext();
    const a = resolveHashtag(emptyRegistry(), "#baddie", ctx);
    const b = resolveHashtag(a.registry, "#boss", ctx);
    expect(b.subject.id).not.toBe(a.subject.id);
  });
});

describe("creator resolution", () => {
  it("resolves the same account_id with different handles to the same Subject", () => {
    const ctx = testContext();
    const first = resolveCreator(emptyRegistry(), { account_id: "123456789", handle: "stephanie" }, ctx);
    const second = resolveCreator(first.registry, { account_id: "123456789", handle: "stephanie_new" }, ctx);
    expect(second.subject.id).toBe(first.subject.id);
    expect(second.created).toBe(false);
    expect(second.registry.subjects).toHaveLength(1);
    // the new handle is only *observed* against the same subject; nothing is renamed or merged
    const handles = second.registry.identities.filter((i) => i.identifier_type === "handle");
    expect(handles.map((h) => h.value).sort()).toEqual(["stephanie", "stephanie_new"]);
    expect(handles.every((h) => h.identity_link_status === "observed")).toBe(true);
  });

  it("falls back to exact handle match when no account_id is known", () => {
    const ctx = testContext();
    const first = resolveCreator(emptyRegistry(), { handle: "stephanie" }, ctx);
    const again = resolveCreator(first.registry, { handle: "stephanie" }, ctx);
    const different = resolveCreator(first.registry, { handle: "Stephanie" }, ctx);
    expect(again.subject.id).toBe(first.subject.id);
    expect(different.subject.id).not.toBe(first.subject.id); // exact, case-sensitive: no similarity matching
  });

  it("never merges: a handle owned by another Subject is flagged, not reassigned", () => {
    const ctx = testContext();
    const a = resolveCreator(emptyRegistry(), { account_id: "1", handle: "alpha" }, ctx);
    const b = resolveCreator(a.registry, { account_id: "2", handle: "beta" }, ctx);
    const clash = resolveCreator(b.registry, { account_id: "2", handle: "alpha" }, ctx);
    expect(clash.subject.id).toBe(b.subject.id);
    expect(clash.conflict).toBe(true);
    expect(clash.registry.subjects).toHaveLength(2);
    expect(clash.registry.identities.filter((i) => i.value === "alpha")).toHaveLength(1);
  });

  it("refuses a display name alone as an identifier", () => {
    expect(() => resolveCreator(emptyRegistry(), {}, testContext())).toThrow();
    expect(() => resolveCreator(emptyRegistry(), { display_name: "Stephanie" }, testContext())).toThrow();
  });
});
