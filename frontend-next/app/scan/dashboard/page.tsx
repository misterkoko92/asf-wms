import { AppShell } from "../../components/app-shell";
import { ScanDashboardLive } from "../../components/scan-dashboard-live";

const timeline = [
  "06:35 Reception palettes RUN",
  "08:15 Preparation EXP-2941",
  "09:40 Litige docs EXP-2937",
  "12:20 Affectation cartons terminee",
  "15:45 Expedition prete a l'envoi",
];

const pendingActions = [
  { label: "Docs manquants", ref: "EXP-2937", owner: "Qualite", due: "now" },
  { label: "Stock faible", ref: "ASF-122", owner: "Magasin", due: "+20m" },
  { label: "Affecter cartons", ref: "EXP-2940", owner: "Warehouse", due: "+35m" },
  { label: "Cloture exped", ref: "EXP-2918", owner: "Qualite", due: "+2h" },
];

export default function ScanDashboardPage() {
  return (
    <AppShell
      section="scan"
      title="Dashboard mission control"
      subtitle="Timeline + actions en attente + creation 1 clic"
    >
      <ScanDashboardLive />
      <div className="kpi-grid">
        <article className="kpi-card">
          <span>Expeditions ouvertes</span>
          <strong>31</strong>
        </article>
        <article className="kpi-card">
          <span>Alertes stock</span>
          <strong>12</strong>
        </article>
        <article className="kpi-card">
          <span>Litiges actifs</span>
          <strong>4</strong>
        </article>
      </div>

      <div className="dashboard-grid">
        <article className="panel">
          <h2>Mission timeline</h2>
          <ul className="timeline-list">
            {timeline.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </article>

        <article className="panel">
          <h2>Actions en attente</h2>
          <table className="data-table">
            <thead>
              <tr>
                <th>Action</th>
                <th>Ref</th>
                <th>Owner</th>
                <th>Due</th>
              </tr>
            </thead>
            <tbody>
              {pendingActions.map((row) => (
                <tr key={row.ref + row.label}>
                  <td>{row.label}</td>
                  <td>{row.ref}</td>
                  <td>{row.owner}</td>
                  <td>{row.due}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="inline-actions">
            <button type="button" className="btn-primary" data-track="scan.create.carton">
              Creer colis
            </button>
            <button type="button" className="btn-secondary" data-track="scan.create.shipment">
              Creer expedition
            </button>
            <button type="button" className="btn-secondary" data-track="scan.add.stock">
              Ajouter stock
            </button>
          </div>
        </article>
      </div>
    </AppShell>
  );
}
