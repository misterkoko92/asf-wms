import { AppShell } from "../../components/app-shell";
import { ScanShipmentsReadyLive } from "../../components/scan-shipments-ready-live";

export default function ShipmentsReadyPage() {
  return (
    <AppShell
      section="scan"
      title="Vue expeditions"
      subtitle="Expeditions ouvertes, documents et acces rapide au suivi"
    >
      <ScanShipmentsReadyLive />
    </AppShell>
  );
}
