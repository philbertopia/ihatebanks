"use client";
import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const nav = [
  { href: "/", label: "Home", icon: "•" },
  { href: "/strategies", label: "Strategies", icon: "🏆" },
  { href: "/backtest", label: "Backtest Explorer", icon: "🧪" },
  { href: "/education", label: "Education", icon: "📚" },
  { href: "/open-source", label: "Open Source", icon: "{}" },
];

export default function Sidebar() {
  const path = usePathname();
  const [open, setOpen] = useState(false);

  const linkClass = (active: boolean) =>
    `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
      active
        ? "bg-gradient-to-r from-blue-600 to-pink-600 text-white shadow-[0_0_0_1px_rgba(236,72,153,0.35)]"
        : "text-gray-400 hover:bg-gray-800 hover:text-pink-200"
    }`;

  const isActive = (href: string) => {
    if (href === "/") return path === "/";
    return path === href || path?.startsWith(`${href}/`);
  };

  return (
    <>
      <header className="lg:hidden fixed top-0 inset-x-0 z-40 h-16 bg-gray-900/95 backdrop-blur border-b border-gray-800 px-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="text-xl">{"\u{1F494}"}</div>
          <div>
            <p className="text-sm font-semibold text-white leading-tight">I Hate Banks</p>
            <p className="text-[11px] text-pink-300/70 leading-tight">Algorithmic Options Strategies</p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="h-9 w-9 rounded-md border border-gray-700 bg-gray-800 text-gray-200 text-lg"
          aria-label="Toggle navigation menu"
        >
          {open ? "×" : "☰"}
        </button>
      </header>

      {open && (
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="lg:hidden fixed inset-0 z-40 bg-black/60"
          aria-label="Close navigation menu"
        />
      )}

      <aside
        className={`lg:hidden fixed top-16 left-0 z-50 h-[calc(100vh-4rem)] w-72 bg-gray-900 border-r border-gray-800 px-4 py-5 flex flex-col gap-1 transform transition-transform ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {nav.map((item) => (
          <Link
            key={`m-${item.href}`}
            href={item.href}
            onClick={() => setOpen(false)}
            className={linkClass(isActive(item.href))}
          >
            <span>{item.icon}</span>
            {item.label}
          </Link>
        ))}
      </aside>

      <aside className="hidden lg:flex w-56 min-h-screen bg-gray-900 border-r border-gray-800 flex-col py-6 px-4 gap-1 shrink-0">
        <div className="mb-6 px-2">
          <div className="text-3xl mb-1">{"\u{1F494}"}</div>
          <h1 className="text-base font-bold text-white tracking-tight leading-tight">I Hate Banks</h1>
          <p className="text-xs text-pink-300/70 mt-1">Algorithmic Options Strategies</p>
        </div>
        {nav.map((item) => (
          <Link key={item.href} href={item.href} className={linkClass(isActive(item.href))}>
            <span>{item.icon}</span>
            {item.label}
          </Link>
        ))}
        <div className="mt-auto px-2 pt-6 border-t border-gray-800">
          <p className="text-xs text-gray-600">5-year backtests</p>
          <p className="text-xs text-gray-600">Walk-forward validated</p>
        </div>
      </aside>
    </>
  );
}
