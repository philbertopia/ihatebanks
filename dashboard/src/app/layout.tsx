import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/Sidebar";
import Footer from "@/components/Footer";

export const metadata: Metadata = {
  title: "I Hate Banks - Open-Source Financial Literacy and Strategy Research",
  description:
    "Built to make financial knowledge accessible: open-source options strategy research, transparent backtests, and educational content for independent learners.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-950 text-gray-100 min-h-screen antialiased lg:flex">
        <Sidebar />
        <main className="min-w-0 min-h-screen lg:flex-1 pt-[calc(5rem+env(safe-area-inset-top))] lg:pt-0 px-4 pb-4 sm:px-6 sm:pb-6 flex flex-col">
          <div className="flex-1">{children}</div>
          <Footer />
        </main>
      </body>
    </html>
  );
}
