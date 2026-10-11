/**
 * JSON-RPC 2.0 client over a newline-delimited text stream.
 * Transport-agnostic: give it a `send` function and feed it stdout chunks.
 */

export class RpcError extends Error {
  constructor(
    readonly code: number,
    message: string,
  ) {
    super(message);
    this.name = "RpcError";
  }
}

type Pending = {
  resolve: (value: unknown) => void;
  reject: (reason: Error) => void;
  timer: ReturnType<typeof setTimeout>;
};

export class RpcClient {
  private nextId = 1;
  private buffer = "";
  private pending = new Map<number, Pending>();

  constructor(
    private readonly send: (line: string) => Promise<void>,
    private readonly timeoutMs = 10_000,
  ) {}

  call<T = unknown>(
    method: string,
    params?: unknown[] | Record<string, unknown>,
    timeoutMs = this.timeoutMs,
  ): Promise<T> {
    const id = this.nextId++;
    const msg = JSON.stringify({ jsonrpc: "2.0", id, method, ...(params ? { params } : {}) });
    return new Promise<T>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`Engine did not answer ${method} within ${timeoutMs} ms`));
      }, timeoutMs);
      this.pending.set(id, { resolve: resolve as (v: unknown) => void, reject, timer });
      this.send(msg + "\n").catch((err: unknown) => {
        clearTimeout(timer);
        this.pending.delete(id);
        reject(err instanceof Error ? err : new Error(String(err)));
      });
    });
  }

  /** Feed raw stdout text; complete lines are parsed and dispatched. */
  feed(chunk: string): void {
    this.buffer += chunk;
    let nl: number;
    while ((nl = this.buffer.indexOf("\n")) >= 0) {
      const line = this.buffer.slice(0, nl).trim();
      this.buffer = this.buffer.slice(nl + 1);
      if (line) this.handleLine(line);
    }
  }

  /** Reject everything in flight, e.g. when the engine process exits. */
  close(reason: string): void {
    for (const [id, p] of this.pending) {
      clearTimeout(p.timer);
      p.reject(new Error(reason));
      this.pending.delete(id);
    }
    this.buffer = "";
  }

  private handleLine(line: string): void {
    let msg: { id?: number; result?: unknown; error?: { code: number; message: string } };
    try {
      msg = JSON.parse(line);
    } catch {
      console.warn("engine: ignoring non-JSON line", line);
      return;
    }
    const p = typeof msg.id === "number" ? this.pending.get(msg.id) : undefined;
    if (!p) return;
    clearTimeout(p.timer);
    this.pending.delete(msg.id!);
    if (msg.error) p.reject(new RpcError(msg.error.code, msg.error.message));
    else p.resolve(msg.result);
  }
}
