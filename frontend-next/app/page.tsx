import Link from "next/link";

export default function LandingPage() {
  return (
    <main className="landing-page">
      <div className="landing-card">
        <h1>ASF WMS - frontend Next en parallele</h1>
        <p>
          Cette application est servie sous <code>/app/*</code> et coexiste avec Benev/Classique.
        </p>
        <div className="landing-actions">
          <Link href="/scan/dashboard" className="btn-primary" data-track="landing.scan">
            Ouvrir Scan dashboard
          </Link>
          <Link href="/portal/dashboard" className="btn-secondary" data-track="landing.portal">
            Ouvrir Portal dashboard
          </Link>
          <a
            className="btn-secondary"
            href="/ui/mode/legacy/?next=%2Fscan%2Fdashboard%2F"
            data-track="landing.legacy"
          >
            Retour interface actuelle
          </a>
        </div>
      </div>
    </main>
  );
}
