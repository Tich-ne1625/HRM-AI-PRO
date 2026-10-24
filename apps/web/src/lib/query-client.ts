import { MutationCache, QueryClient } from "@tanstack/react-query";

export function createQueryClient() {
  const client: QueryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    mutationCache: new MutationCache({
      // Failed requests may still commit a terminal AI attempt. Only refetch GET views;
      // never retry a mutation or generate advice as a side effect of refreshing.
      onSettled: () => Promise.all([
        client.invalidateQueries({ queryKey: ["dashboard"] }),
        client.invalidateQueries({ queryKey: ["ai", "reports"] }),
      ]).then(() => undefined),
    }),
  });
  return client;
}
