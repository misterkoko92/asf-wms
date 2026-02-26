import { AppShell } from "../../components/app-shell";

export default function ScanFaqPage() {
  return (
    <AppShell
      section="scan"
      title="FAQ / Documentation"
      subtitle="Reference metier WMS Scan pour les flux stock, colis et expeditions"
    >
      <div className="stack-grid">
        <article className="panel">
          <h2>Vue d'ensemble</h2>
          <p className="panel-note">
            Cette page decrit le fonctionnement complet du WMS Scan, du stock a l expedition.
          </p>
          <ul>
            <li>Produit: fiche article (SKU, nom, marque, emplacement).</li>
            <li>Lot: stock reel par produit (quantite, peremption, lot, emplacement).</li>
            <li>Carton: unite de preparation reliee aux flux expedition.</li>
            <li>Expedition: regroupe des cartons pour une destination.</li>
            <li>Suivi expedition: journal des scans QR avec horodatage.</li>
          </ul>
        </article>

        <article className="panel">
          <h2>Acces et roles</h2>
          <ul>
            <li>Les pages /scan internes sont reservees aux utilisateurs staff.</li>
            <li>Imports et Templates restent limites aux superusers.</li>
            <li>Le suivi public par token reste accessible sans login.</li>
          </ul>
        </article>

        <article className="panel">
          <h2>Flux critiques</h2>
          <ul>
            <li>Vue stock: recherche multi-cles + filtres + tri.</li>
            <li>Preparation colis: creation, affectation, etiquetage.</li>
            <li>Expeditions: brouillon, planification, suivi, cloture dossier.</li>
            <li>Documents & labels: generation et uploads additionnels.</li>
          </ul>
        </article>

        <article className="panel">
          <h2>Notes de migration Next</h2>
          <p className="panel-note">
            Cette route remplace l ecran legacy <code>/scan/faq/</code> en parite fonctionnelle.
          </p>
        </article>
      </div>
    </AppShell>
  );
}
