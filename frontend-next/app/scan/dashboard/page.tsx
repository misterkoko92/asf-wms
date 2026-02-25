import { AppShell } from "../../components/app-shell";
import { ScanDashboardLive } from "../../components/scan-dashboard-live";

export default function ScanDashboardPage() {
  return (
    <AppShell
      section="scan"
      title="Dashboard mission control"
      subtitle="Timeline + actions en attente + creation 1 clic"
    >
      <ScanDashboardLive />
    </AppShell>
  );
}
