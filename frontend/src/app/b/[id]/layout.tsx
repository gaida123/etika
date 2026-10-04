import { AppShell } from "@/components/business/AppShell";
import { BusinessProvider } from "@/components/business/BusinessProvider";

export default async function BusinessLayout({ children, params }: LayoutProps<"/b/[id]">) {
  const { id } = await params;
  return (
    <BusinessProvider businessId={id}>
      <AppShell>{children}</AppShell>
    </BusinessProvider>
  );
}
