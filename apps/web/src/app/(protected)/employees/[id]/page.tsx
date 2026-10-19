import { EmployeeDetail } from "../../../../features/organization/employee-detail";
export default async function EmployeePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <EmployeeDetail id={id} />;
}
