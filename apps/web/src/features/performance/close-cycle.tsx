"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { Cycle } from "../cycles/api";
import { ReviewError } from "../cycles/shared";
import { performanceApi } from "./api";

export function CloseCycle({ cycle }: { cycle: Cycle }) {
  const cache = useQueryClient();
  const [version, setVersion] = useState<number | null>(null);
  const mutation = useMutation({ mutationFn: (expected: number) => performanceApi.close(cycle.id, expected), onSuccess: async () => { setVersion(null); await Promise.all(["reviews", "performance", "feedback"].map((key) => cache.invalidateQueries({ queryKey: [key] }))); } });
  return <><button className="secondary" onClick={() => setVersion(cycle.version)}>Đóng chu kỳ</button>
    {version !== null && <section className="confirmation" role="group" aria-label="Xác nhận đóng chu kỳ"><p>Chỉ đóng được khi mọi người tham gia đã chốt kết quả. Sau khi đóng, chu kỳ được lưu để tra cứu và không mở lại.</p><div className="row-actions"><button disabled={mutation.isPending || mutation.isError} onClick={() => mutation.mutate(version)}>Xác nhận đóng chu kỳ</button><button className="secondary" disabled={mutation.isPending} onClick={() => { setVersion(null); mutation.reset(); }}>Hủy</button></div></section>}
    {mutation.isError && <ReviewError error={mutation.error} reload={() => { setVersion(null); mutation.reset(); void cache.invalidateQueries({ queryKey: ["reviews"] }); }} />}
  </>;
}
