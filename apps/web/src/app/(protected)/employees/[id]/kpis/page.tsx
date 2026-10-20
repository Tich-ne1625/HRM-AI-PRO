import { EmployeeKpis } from "../../../../../features/kpis/employee-kpis";
export default async function Page({params, searchParams}: {params: Promise<{id: string}>; searchParams: Promise<{cycle_id?: string}>}) {
  const [{id}, search] = await Promise.all([params, searchParams]);
  return <EmployeeKpis id={id} cycle={typeof search.cycle_id === "string" ? search.cycle_id : ""} />;
}
