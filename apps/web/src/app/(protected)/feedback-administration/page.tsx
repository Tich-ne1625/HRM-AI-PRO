import { FeedbackAdministration } from "../../../features/feedback/administration";

export default async function AdministrationPage({ searchParams }: { searchParams: Promise<{ participant_id?: string; cycle_id?: string }> }) {
  const { participant_id, cycle_id } = await searchParams;
  return <FeedbackAdministration key={`${participant_id}-${cycle_id}`} participantId={participant_id} cycleId={cycle_id} />;
}
