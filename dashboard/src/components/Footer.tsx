import Link from "next/link";
import LegalDisclaimer from "@/components/LegalDisclaimer";

const quickLinks = [
  { href: "/", label: "Home" },
  { href: "/strategies", label: "Strategies" },
  { href: "/backtest", label: "Backtest Explorer" },
  { href: "/education", label: "Education" },
];

export default function Footer() {
  return (
    <footer className="mt-10 sm:mt-14 border-t border-gray-800 pt-6 pb-2">
      <div className="max-w-5xl mx-auto flex flex-col sm:flex-row sm:items-start sm:justify-between gap-6">
        <div className="max-w-xl">
          <div className="flex items-center gap-2">
            <span className="text-lg">{"\u{1F494}"}</span>
            <p className="text-sm font-semibold text-white">I Hate Banks</p>
          </div>
          <p className="text-xs text-gray-500 mt-2 mb-3">
            Open research in algorithmic options strategies.
          </p>
          <LegalDisclaimer compact />
        </div>

        <nav aria-label="Footer links">
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Links</p>
          <ul className="space-y-1.5">
            {quickLinks.map((link) => (
              <li key={link.href}>
                <Link
                  href={link.href}
                  className="text-sm text-gray-300 hover:text-pink-300 transition-colors"
                >
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </footer>
  );
}
