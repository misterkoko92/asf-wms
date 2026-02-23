import { AppShell } from "../../components/app-shell";
import { ScanShipmentDocumentsLive } from "../../components/scan-shipment-documents-live";

export default function ShipmentDocumentsPage() {
  return (
    <AppShell
      section="scan"
      title="Documents et labels expedition"
      subtitle="Upload, suppression et impression des labels depuis la couche API UI P2"
    >
      <article className="panel">
        <h2>Gestion documents/labels</h2>
        <p className="panel-note">
          Cette vue utilise les endpoints <code>/api/v1/ui/shipments/*/documents</code> et{" "}
          <code>/api/v1/ui/shipments/*/labels</code>.
        </p>
        <ScanShipmentDocumentsLive />
      </article>
    </AppShell>
  );
}
