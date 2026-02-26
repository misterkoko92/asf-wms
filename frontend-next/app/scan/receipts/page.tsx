import { AppShell } from "../../components/app-shell";
import { ScanReceiptsLive } from "../../components/scan-receipts-live";

export default function ScanReceiptsPage() {
  return (
    <AppShell
      section="scan"
      title="Vue reception"
      subtitle="Liste des receptions avec filtre type et synthese quantites"
    >
      <ScanReceiptsLive />
    </AppShell>
  );
}
