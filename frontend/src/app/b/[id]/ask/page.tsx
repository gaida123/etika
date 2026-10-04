import { AskFull } from "@/components/business/AskFull";

export default async function AskPage({ searchParams }: PageProps<"/b/[id]/ask">) {
  const { topic } = await searchParams;
  return <AskFull topic={typeof topic === "string" ? topic : null} />;
}
