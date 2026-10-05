import "./globals.css";
import type { ReactNode } from "react";
import Nav from "./nav";

export const metadata = {
  title: "Epidemic Risk Map",
  description: "Coursework analytics demo with aggregate data and illustrative geographic zones, not a public-health service.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Nav />
        <aside className="demoNotice">Coursework demo. Aggregate snapshots only. Map zones are illustrative, not real outbreak locations. No medical advice.</aside>
        {children}
      </body>
    </html>
  );
}
