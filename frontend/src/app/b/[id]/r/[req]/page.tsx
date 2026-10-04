import { FindingView } from "@/components/business/FindingView";

export default async function RequirementPage({ params }: PageProps<"/b/[id]/r/[req]">) {
  const { req } = await params;
  return <FindingView requirementId={req} />;
}
