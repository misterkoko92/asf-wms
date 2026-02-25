import { AppShell } from "../../components/app-shell";
import { ScanShipmentTrackingLive } from "../../components/scan-shipment-tracking-live";

const trackingHints = [
  "Planification confirmee",
  "Mise a bord confirmee",
  "Recu escale correspondant",
  "Recu destinataire",
];

export default function ShipmentsTrackingPage() {
  return (
    <AppShell
      section="scan"
      title="Suivi des expeditions"
      subtitle="Mise a jour des etapes de tracking et cloture dossier"
    >
      <ScanShipmentTrackingLive />
      <article className="panel">
        <h2>Etapes attendues</h2>
        <ul className="check-list">
          {trackingHints.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </article>
    </AppShell>
  );
}
