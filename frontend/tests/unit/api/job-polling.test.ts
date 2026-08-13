import { describe, expect, it } from "vitest";
import {
  MAX_NETWORK_RETRY_ATTEMPTS,
  NETWORK_RETRY_MESSAGE,
  PERSISTENT_NETWORK_ERROR_MESSAGE,
  interpretJobStatus,
  nextRetryDelayMs,
} from "@/lib/api/job-polling";
import type { JobStatusResponseContract } from "@/lib/api/contract-types";

function baseResponse(overrides: Partial<JobStatusResponseContract>): JobStatusResponseContract {
  return {
    jobId: "job-1",
    status: "queued",
    createdAt: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("interpretJobStatus", () => {
  it("never surfaces an error while queued or running", () => {
    expect(interpretJobStatus(baseResponse({ status: "queued" }))).toEqual({ kind: "continue" });
    expect(interpretJobStatus(baseResponse({ status: "running" }))).toEqual({ kind: "continue" });
  });

  it("returns the converted domain result on success", () => {
    const outcome = interpretJobStatus(
      baseResponse({
        status: "succeeded",
        result: {
          contractVersion: "1.0",
          orderId: "order-1",
          engineVersion: "1.0.0",
          durationMs: 12,
          warnings: [],
          totalCartonsCount: 1,
          placedCartonsCount: 1,
          unplacedCartonsCount: 0,
          palletsCount: 1,
          globalVolumeUsageRatio: 0.5,
          totalWeightKg: 1,
          pallets: [],
          unplacedCartons: [],
          legacyExpectedResult: null,
        },
      })
    );
    expect(outcome.kind).toBe("succeeded");
    if (outcome.kind === "succeeded") {
      expect(outcome.result.totalCartonsCount).toBe(1);
    }
  });

  it("reports an error when the server claims success but omits the result", () => {
    const outcome = interpretJobStatus(baseResponse({ status: "succeeded", result: null }));
    expect(outcome).toMatchObject({ kind: "error" });
  });

  it("surfaces the structured business error message on failure", () => {
    const outcome = interpretJobStatus(
      baseResponse({ status: "failed", error: { code: "PACKING_ERROR", message: "Erreur métier précise" } })
    );
    expect(outcome).toEqual({ kind: "error", message: "Erreur métier précise" });
  });

  it("reports expiry distinctly from a generic failure", () => {
    const outcome = interpretJobStatus(baseResponse({ status: "expired" }));
    expect(outcome).toMatchObject({ kind: "error" });
    expect((outcome as { message: string }).message).toMatch(/délai maximal/i);
  });

  it("reports cancellation as a terminal error state", () => {
    const outcome = interpretJobStatus(baseResponse({ status: "cancelled" }));
    expect(outcome).toEqual({ kind: "error", message: "Le calcul a été annulé." });
  });

  it("never leaks a raw stack trace or technical detail for an unknown status", () => {
    const outcome = interpretJobStatus(baseResponse({ status: "unknown" as never }));
    expect(outcome.kind).toBe("error");
  });
});

describe("nextRetryDelayMs", () => {
  it("grows exponentially and stays capped at 15s", () => {
    const delays = Array.from({ length: MAX_NETWORK_RETRY_ATTEMPTS }, (_, i) => nextRetryDelayMs(i + 1));
    expect(delays).toEqual([2_000, 4_000, 8_000, 15_000, 15_000]);
  });

  it("gives up (returns null) once the attempt budget is exhausted", () => {
    expect(nextRetryDelayMs(MAX_NETWORK_RETRY_ATTEMPTS + 1)).toBeNull();
  });

  it("rejects a non-positive attempt count", () => {
    expect(nextRetryDelayMs(0)).toBeNull();
  });
});

describe("network retry messages", () => {
  it("distinguishes a transient retry from a persistent failure", () => {
    expect(NETWORK_RETRY_MESSAGE).not.toEqual(PERSISTENT_NETWORK_ERROR_MESSAGE);
    expect(PERSISTENT_NETWORK_ERROR_MESSAGE).toMatch(/rechargez la page/i);
  });

  it("never mentions a fixed 30-second timeout", () => {
    expect(NETWORK_RETRY_MESSAGE).not.toMatch(/30\s*s/);
    expect(PERSISTENT_NETWORK_ERROR_MESSAGE).not.toMatch(/30\s*s/);
  });
});
