import { AppShell } from "../../components/app-shell";
import { ScanCartonsLive } from "../../components/scan-cartons-live";

export default function CartonsPage() {
  return (
    <AppShell
      section="scan"
      title="Vue colis"
      subtitle="Suivi des colis conditionnes avec acces impression et picking"
    >
      <ScanCartonsLive />
    </AppShell>
  );
}
