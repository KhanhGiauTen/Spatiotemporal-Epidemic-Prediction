import "./globals.css";
import type { ReactNode } from "react";
import Nav from "./nav";

export const metadata = {
  title: "Epidemic Risk Map",
  description: "Interactive map for predicted outbreak risk polygons",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Nav />
        {children}
      </body>
    </html>
  );
}
