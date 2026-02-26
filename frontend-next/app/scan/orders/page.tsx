import { AppShell } from "../../components/app-shell";
import { ScanOrdersLive } from "../../components/scan-orders-live";

export default function ScanOrdersPage() {
  return (
    <AppShell
      section="scan"
      title="Vue commandes"
      subtitle="Suivi commandes associations, revue statut et creation expedition"
    >
      <ScanOrdersLive />
    </AppShell>
  );
}
