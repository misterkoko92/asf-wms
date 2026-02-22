import type { Metadata } from "next";

import { FrontendLogger } from "./components/frontend-logger";
import "./globals.css";

export const metadata: Metadata = {
  title: "ASF WMS Next (parallel)",
  description: "Shell Next statique en parallele de Benev/Classique",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="fr">
      <body>
        <FrontendLogger />
        {children}
      </body>
    </html>
  );
}
