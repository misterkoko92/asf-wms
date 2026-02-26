import { Suspense } from "react";

import { AppShell } from "../../components/app-shell";
import { ScanOrderLive } from "../../components/scan-order-live";

export default function ScanOrderPage() {
  return (
    <AppShell
      section="scan"
      title="Commande scan"
      subtitle="Creation et preparation commande avec reservation de stock"
    >
      <Suspense fallback={<div className="api-state">Chargement commande scan...</div>}>
        <ScanOrderLive />
      </Suspense>
    </AppShell>
  );
}
