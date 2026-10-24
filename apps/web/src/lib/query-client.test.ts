import { MutationObserver, QueryObserver } from "@tanstack/react-query";
import { expect, it, vi } from "vitest";
import { createQueryClient } from "./query-client";

it.each([false, true])("refreshes dashboard and saved reports after a mutation (failure=%s) without retrying it", async (fails) => {
  const client = createQueryClient();
  const dashboardRead = vi.fn().mockResolvedValue({ participants: 1 });
  const reportsRead = vi.fn().mockResolvedValue({ total: 1 });
  const dashboard = new QueryObserver(client, { queryKey: ["dashboard", "u1"], queryFn: dashboardRead });
  const reports = new QueryObserver(client, { queryKey: ["ai", "reports", "u1"], queryFn: reportsRead });
  const unsub = [dashboard.subscribe(() => {}), reports.subscribe(() => {})];
  await Promise.all([dashboard.refetch(), reports.refetch()]);
  const before = [dashboardRead.mock.calls.length, reportsRead.mock.calls.length];
  const mutationFn = vi.fn(async () => { if (fails) throw new Error("lost response"); return {}; });
  const mutation = new MutationObserver(client, { mutationFn });
  if (fails) await expect(mutation.mutate()).rejects.toThrow("lost response");
  else await mutation.mutate();
  expect(mutationFn).toHaveBeenCalledTimes(1);
  expect(dashboardRead.mock.calls.length).toBeGreaterThan(before[0]!);
  expect(reportsRead.mock.calls.length).toBeGreaterThan(before[1]!);
  unsub.forEach((stop) => stop()); client.clear();
});
