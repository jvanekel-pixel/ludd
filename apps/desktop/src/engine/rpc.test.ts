import { describe, expect, it, vi } from "vitest";
import { RpcClient, RpcError } from "./rpc";

/** A fake engine that answers each request line through `respond`. */
function fakeEngine(respond: (req: { id: number; method: string }) => object | null) {
  const sent: string[] = [];
  const client: RpcClient = new RpcClient(async (line) => {
    sent.push(line);
    const res = respond(JSON.parse(line));
    if (res) queueMicrotask(() => client.feed(JSON.stringify(res) + "\n"));
  }, 50);
  return { client, sent };
}

describe("RpcClient", () => {
  it("resolves a ping", async () => {
    const { client, sent } = fakeEngine((r) => ({ jsonrpc: "2.0", id: r.id, result: "pong" }));
    await expect(client.call("ping")).resolves.toBe("pong");
    expect(JSON.parse(sent[0])).toEqual({ jsonrpc: "2.0", id: 1, method: "ping" });
    expect(sent[0].endsWith("\n")).toBe(true);
  });

  it("rejects with RpcError on an error response", async () => {
    const { client } = fakeEngine((r) => ({
      jsonrpc: "2.0",
      id: r.id,
      error: { code: -32601, message: "Method not found: nope" },
    }));
    const err = (await client.call("nope").catch((e: unknown) => e)) as RpcError;
    expect(err).toBeInstanceOf(RpcError);
    expect(err.code).toBe(-32601);
  });

  it("reassembles responses split across chunks and out of order", async () => {
    const client = new RpcClient(async () => {}, 1000);
    const a = client.call("a");
    const b = client.call("b");
    client.feed('{"jsonrpc":"2.0","id":2,"res');
    client.feed('ult":"B"}\n{"jsonrpc":"2.0",');
    client.feed('"id":1,"result":"A"}\n');
    await expect(a).resolves.toBe("A");
    await expect(b).resolves.toBe("B");
  });

  it("ignores non-JSON lines", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const { client } = fakeEngine((r) => ({ jsonrpc: "2.0", id: r.id, result: 1 }));
    client.feed("some log noise\n");
    await expect(client.call("x")).resolves.toBe(1);
    warn.mockRestore();
  });

  it("times out when the engine is silent", async () => {
    const { client } = fakeEngine(() => null);
    await expect(client.call("ping")).rejects.toThrow(/did not answer ping/);
  });

  it("rejects in-flight calls on close", async () => {
    const { client } = fakeEngine(() => null);
    const p = client.call("ping");
    client.close("engine exited");
    await expect(p).rejects.toThrow("engine exited");
  });
});
