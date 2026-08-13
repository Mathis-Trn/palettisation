import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Simulation } from "@/domain/types";
import { defaultSettings } from "@/store/simulation-store";

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

function testSimulation(): Simulation {
  return {
    id: "sim-1",
    name: "Test",
    createdAtIso: "2026-01-01T00:00:00Z",
    updatedAtIso: "2026-01-01T00:00:00Z",
    settings: defaultSettings(),
    cartonLines: [],
    storageVersion: 1,
  };
}

describe("createPalletizationJob", () => {
  it("POSTs to the versioned jobs endpoint and returns the 202 envelope, never blocking on the result", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ jobId: "job-abc", status: "queued", createdAt: "2026-01-01T00:00:01Z" }),
        { status: 202, headers: { "Content-Type": "application/json" } }
      )
    );
    vi.stubGlobal("fetch", fetchMock);

    const { createPalletizationJob } = await import("@/lib/api/client");
    const created = await createPalletizationJob(testSimulation());

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/palletization-jobs",
      expect.objectContaining({ method: "POST" })
    );
    expect(created).toEqual({ jobId: "job-abc", status: "queued", createdAt: "2026-01-01T00:00:01Z" });
  });
});

describe("getPalletizationJob", () => {
  it("GETs the job by id, url-encoded", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ jobId: "job/weird id", status: "running", createdAt: "2026-01-01T00:00:01Z" }),
        { status: 200 }
      )
    );
    vi.stubGlobal("fetch", fetchMock);

    const { getPalletizationJob } = await import("@/lib/api/client");
    await getPalletizationJob("job/weird id");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/palletization-jobs/job%2Fweird%20id",
      expect.objectContaining({ method: "GET" })
    );
  });

  it("propagates a structured 404 as an ApiError for an unknown job", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ error: { code: "JOB_NOT_FOUND", message: "Job introuvable." } }),
        { status: 404 }
      )
    );
    vi.stubGlobal("fetch", fetchMock);

    const { getPalletizationJob, ApiError } = await import("@/lib/api/client");
    await expect(getPalletizationJob("missing")).rejects.toBeInstanceOf(ApiError);
    await expect(getPalletizationJob("missing")).rejects.toMatchObject({ status: 404 });
  });
});

describe("cancelPalletizationJob", () => {
  it("DELETEs the job by id", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ jobId: "job-abc", status: "cancelled", createdAt: "2026-01-01T00:00:01Z" }),
        { status: 200 }
      )
    );
    vi.stubGlobal("fetch", fetchMock);

    const { cancelPalletizationJob } = await import("@/lib/api/client");
    await cancelPalletizationJob("job-abc");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/palletization-jobs/job-abc",
      expect.objectContaining({ method: "DELETE" })
    );
  });
});

describe("request timeout configuration", () => {
  it("times out per NEXT_PUBLIC_API_REQUEST_TIMEOUT_MS, never a hardcoded 30s", async () => {
    // Timeout configuré volontairement très court pour ce test : évite d'attendre 15s réelles
    // (ou pire, 30s) juste pour vérifier que l'abandon se déclenche bien via AbortController.
    process.env.NEXT_PUBLIC_API_REQUEST_TIMEOUT_MS = "20";
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string, init?: RequestInit) => {
        return new Promise((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => {
            const error = new DOMException("aborted", "AbortError");
            reject(error);
          });
        });
      })
    );
    const { getPalletizationJob, ApiError } = await import("@/lib/api/client");
    const error = await getPalletizationJob("job-abc").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as InstanceType<typeof ApiError>).code).toBe("TIMEOUT");
    expect((error as Error).message).not.toMatch(/\(30s\)/);
    expect((error as Error).message).toMatch(/\(0\.02s\)/);
  });
});
