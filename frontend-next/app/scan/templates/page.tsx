import { AppShell } from "../../components/app-shell";
import { ScanPrintTemplatesLive } from "../../components/scan-print-templates-live";

export default function ScanTemplatesPage() {
  return (
    <AppShell
      section="scan"
      title="Templates impression"
      subtitle="Edition versionnee des layouts avec fallback legacy"
    >
      <article className="panel">
        <h2>Editeur templates</h2>
        <p className="panel-note">
          Endpoint superuser: <code>/api/v1/ui/templates/*</code>.
        </p>
        <ScanPrintTemplatesLive />
      </article>
    </AppShell>
  );
}
