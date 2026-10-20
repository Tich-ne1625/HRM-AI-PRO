import { CycleDetail } from "../../../../features/cycles/cycle-detail";
export default async function Page({params}: {params: Promise<{id: string}>}) {
  const {id} = await params;
  return <CycleDetail id={id} />;
}
