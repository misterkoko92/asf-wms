import { AppShell } from "../../components/app-shell";
import { ScanShipmentOptionsLive } from "../../components/scan-shipment-options-live";

const checklist = [
  "Cartons crees",
  "Cartons assignes",
  "Escale selectionnee",
  "Expediteur renseigne",
  "Destinataire renseigne",
  "Correspondant renseigne",
  "Documents attaches",
];

export default function ShipmentCreatePage() {
  return (
    <AppShell
      section="scan"
      title="Creation expedition"
      subtitle="Single page avec guardrails obligatoires avant etat prete a l'envoi"
    >
      <ScanShipmentOptionsLive />
      <article className="panel">
        <h2>Checklist obligatoire</h2>
        <ul className="check-list">
          {checklist.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </article>
    </AppShell>
  );
}
