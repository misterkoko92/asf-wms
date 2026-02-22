import { AppShell } from "../../components/app-shell";

const stockRows = [
  { product: "Sterile dressing", brand: "MediCare", location: "Rack B2", qty: 17, state: "LOW" },
  { product: "Insulin rapid", brand: "Novo", location: "Cold C1", qty: 31, state: "OK" },
  { product: "Perfuser", brand: "FlowMed", location: "Rack C4", qty: 8, state: "CRIT" },
  { product: "Syringe 5ml", brand: "MediCare", location: "Rack D2", qty: 12, state: "LOW" },
  { product: "Gloves M", brand: "SafeHands", location: "Rack A1", qty: 44, state: "OK" },
];

export default function ScanStockPage() {
  return (
    <AppShell
      section="scan"
      title="Vue stock"
      subtitle="Table orientee action avec batch, scan continu et mode offline"
    >
      <article className="panel">
        <div className="panel-head">
          <h2>Stock principal</h2>
          <div className="inline-actions">
            <button type="button" className="btn-secondary" data-track="stock.scan">
              Scan
            </button>
            <button type="button" className="btn-secondary" data-track="stock.batch.update">
              Batch update
            </button>
            <button type="button" className="btn-secondary" data-track="stock.offline">
              Offline
            </button>
          </div>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Produit</th>
              <th>Marque</th>
              <th>Emplacement</th>
              <th>Qty</th>
              <th>Etat</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {stockRows.map((row) => (
              <tr key={row.product}>
                <td>{row.product}</td>
                <td>{row.brand}</td>
                <td>{row.location}</td>
                <td>{row.qty}</td>
                <td>
                  <span className={`state-pill state-${row.state.toLowerCase()}`}>{row.state}</span>
                </td>
                <td>
                  <button type="button" className="table-action" data-track="stock.update.inline">
                    MAJ
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
