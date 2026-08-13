import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const ORIGINAL_ENV = process.env.NEXT_PUBLIC_PALLETIZER_API_URL;

beforeEach(() => {
  process.env.NEXT_PUBLIC_PALLETIZER_API_URL = "http://localhost:8000";
  vi.resetModules();
});

afterEach(() => {
  process.env.NEXT_PUBLIC_PALLETIZER_API_URL = ORIGINAL_ENV;
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("healthCheck", () => {
  it("calls GET /health on the configured base URL", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok", version: "1.0.0", engineVersion: "1.0.0" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const { healthCheck } = await import("@/lib/api/client");
    const result = await healthCheck();

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/health",
      expect.objectContaining({ method: "GET" })
    );
    expect(result.status).toBe("ok");
  });
});

describe("error handling", () => {
  it("throws a structured ApiError with the backend's error envelope on a non-2xx response", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ error: { code: "VALIDATION_ERROR", message: "Champ manquant", correlation_id: "abc-123" } }),
        { status: 422 }
      )
    );
    vi.stubGlobal("fetch", fetchMock);

    const { getCapabilities, ApiError } = await import("@/lib/api/client");
    await expect(getCapabilities()).rejects.toMatchObject({
      name: "ApiError",
      status: 422,
      code: "VALIDATION_ERROR",
      correlationId: "abc-123",
    });
    await expect(getCapabilities()).rejects.toBeInstanceOf(ApiError);
  });

  it("throws a network ApiError when fetch itself rejects (backend unreachable)", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    vi.stubGlobal("fetch", fetchMock);

    const { healthCheck } = await import("@/lib/api/client");
    await expect(healthCheck()).rejects.toMatchObject({ code: "NETWORK_ERROR" });
  });

  it("throws a MISSING_API_URL error when the env var is not configured", async () => {
    delete process.env.NEXT_PUBLIC_PALLETIZER_API_URL;
    vi.stubGlobal("fetch", vi.fn());

    const { healthCheck } = await import("@/lib/api/client");
    await expect(healthCheck()).rejects.toMatchObject({ code: "MISSING_API_URL" });
  });
});

describe("parseCsv", () => {
  it("uploads the file as multipart form data", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          contractVersion: "1.0",
          orders: [],
          errors: [],
          warnings: [],
          totalRows: 0,
          acceptedRows: 0,
          rejectedRows: 0,
          stats: { ordersCount: 0, palletFormats: [], shippingModes: [] },
        }),
        { status: 200 }
      )
    );
    vi.stubGlobal("fetch", fetchMock);

    const { parseCsv } = await import("@/lib/api/client");
    const file = new File(["a;b\n1;2"], "commande.csv", { type: "text/csv" });
    await parseCsv(file);

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/v1/orders/parse-csv");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
  });
});
