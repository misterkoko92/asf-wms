import { AppShell } from "../../components/app-shell";
import { ScanStockLive } from "../../components/scan-stock-live";

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
        <ScanStockLive />
      </article>
    </AppShell>
  );
}
