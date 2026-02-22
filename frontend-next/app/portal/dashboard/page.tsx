import { AppShell } from "../../components/app-shell";

const orders = [
  { reference: "CMD-2026-0217", destination: "RUN", status: "Pending docs" },
  { reference: "CMD-2026-0218", destination: "NCE", status: "Ready" },
  { reference: "CMD-2026-0219", destination: "TNR", status: "In review" },
];

export default function PortalDashboardPage() {
  return (
    <AppShell
      section="portal"
      title="Portal dashboard"
      subtitle="Vue simplifiee association pour commandes et progression documentaire"
    >
      <div className="kpi-grid">
        <article className="kpi-card">
          <span>Commandes ouvertes</span>
          <strong>24</strong>
        </article>
        <article className="kpi-card">
          <span>Docs en attente</span>
          <strong>7</strong>
        </article>
        <article className="kpi-card">
          <span>Risque litige</span>
          <strong>3</strong>
        </article>
      </div>
      <article className="panel">
        <h2>Commandes recentes</h2>
        <table className="data-table">
          <thead>
            <tr>
              <th>Ref</th>
              <th>Destination</th>
              <th>Statut</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {orders.map((row) => (
              <tr key={row.reference}>
                <td>{row.reference}</td>
                <td>{row.destination}</td>
                <td>{row.status}</td>
                <td>
                  <button type="button" className="table-action" data-track="portal.order.open">
                    Ouvrir
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </article>
    </AppShell>
  );
}
