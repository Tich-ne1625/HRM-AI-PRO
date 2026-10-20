import { FeedbackDetail } from "../../../../features/feedback/detail";

export default async function FeedbackDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <FeedbackDetail key={id} id={id} />;
}
