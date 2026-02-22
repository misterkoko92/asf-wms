import { AppShell } from "../../components/app-shell";

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
      <div className="shipment-grid">
        <article className="panel">
          <h2>Checklist obligatoire</h2>
          <ul className="check-list">
            {checklist.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </article>

        <article className="panel">
          <h2>Formulaire expedition</h2>
          <div className="form-grid">
            <label>
              Destination
              <input defaultValue="RUN" />
            </label>
            <label>
              Escale livraison
              <input defaultValue="Escale Nord" />
            </label>
            <label>
              Expediteur
              <input defaultValue="ASF Paris Hub" />
            </label>
            <label>
              Destinataire
              <input defaultValue="CHU Nord" />
            </label>
            <label>
              Correspondant
              <input defaultValue="Marie Dupont" />
            </label>
            <label>
              Date demandee
              <input defaultValue="2026-02-25" />
            </label>
          </div>
        </article>

        <article className="panel">
          <h2>Etat documents</h2>
          <table className="data-table">
            <tbody>
              <tr>
                <td>Packing list expedition</td>
                <td>OK</td>
              </tr>
              <tr>
                <td>Packing list carton</td>
                <td>OK</td>
              </tr>
              <tr>
                <td>Attestation donation</td>
                <td>OK</td>
              </tr>
              <tr>
                <td>Bon de livraison</td>
                <td>Missing</td>
              </tr>
              <tr>
                <td>Attestation douane</td>
                <td>OK</td>
              </tr>
            </tbody>
          </table>
        </article>
      </div>

      <div className="inline-actions">
        <button type="button" className="btn-secondary" data-track="shipment.save">
          Save draft
        </button>
        <button type="button" className="btn-secondary" data-track="shipment.publish.warn">
          Publish warning
        </button>
        <button type="button" className="btn-primary" data-track="shipment.ready">
          Set ready to ship
        </button>
      </div>
    </AppShell>
  );
}
