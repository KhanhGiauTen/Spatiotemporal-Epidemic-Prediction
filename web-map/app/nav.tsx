"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/", label: "Overview" },
  { href: "/risk-map", label: "Risk Map" },
  { href: "/prediction", label: "Prediction" },
  { href: "/clusters", label: "Clusters" },
  { href: "/network", label: "Network" },
  { href: "/about", label: "About" },
];

export default function Nav() {
  const pathname = usePathname();

  return (
    <nav className="nav">
      <div className="brand">Epidemic Monitor</div>
      <div className="navLinks">
        {links.map((link) => (
          <Link className={pathname === link.href ? "active" : ""} href={link.href} key={link.href}>
            {link.label}
          </Link>
        ))}
      </div>
    </nav>
  );
}
