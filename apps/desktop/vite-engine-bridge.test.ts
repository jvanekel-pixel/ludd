import { describe, expect, it } from "vitest";
import { allowedRequest, MAX_BODY_BYTES, planRequest } from "./vite-engine-bridge";

describe("dev engine bridge requests (Phase 1 audit)", () => {
  it("passes a notification through without waiting for an answer that never comes", () => {
    expect(planRequest('{"jsonrpc":"2.0","method":"ping"}').kind).toBe("notify");
    expect(planRequest('{"jsonrpc":"2.0","method":"ping","id":null}').kind).toBe("notify");
  });

  it("makes a call when there is an id, and refuses junk", () => {
    expect(planRequest('{"jsonrpc":"2.0","method":"ping","id":7}')).toEqual({ kind: "call", msg: { jsonrpc: "2.0", method: "ping", id: 7 } });
    expect(planRequest("not json").kind).toBe("bad");
    expect(planRequest("[1,2]").kind).toBe("bad");
    expect(planRequest("null").kind).toBe("bad");
  });

  it("has a size limit that still fits a project with pictures", () => {
    expect(MAX_BODY_BYTES).toBeGreaterThanOrEqual(768 * 1024 * 1024);
  });
});

describe("dev engine bridge (QA packaging: any web site could post to it)", () => {
  it("answers the preview page on this machine", () => {
    expect(allowedRequest({ host: "localhost:1420", origin: "http://localhost:1420" })).toBe(true);
    expect(allowedRequest({ host: "127.0.0.1:1420", origin: "http://127.0.0.1:1420" })).toBe(true);
    expect(allowedRequest({ host: "localhost:1420" })).toBe(true);
  });

  it("refuses other sites and names pointed at this machine", () => {
    expect(allowedRequest({ host: "localhost:1420", origin: "https://example.invalid" })).toBe(false);
    expect(allowedRequest({ host: "localhost:1420", origin: "null" })).toBe(false);
    expect(allowedRequest({ host: "evil.example:1420", origin: "http://evil.example:1420" })).toBe(false);
    expect(allowedRequest({})).toBe(false);
  });
});
