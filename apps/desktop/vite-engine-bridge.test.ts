import { describe, expect, it } from "vitest";
import { allowedRequest } from "./vite-engine-bridge";

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
