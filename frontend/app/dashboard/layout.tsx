"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  const navItems = [
    { name: "Hive", path: "/dashboard/hive" },
    { name: "Workers", path: "/dashboard/workers" },
    { name: "Market", path: "/dashboard/market" },
    { name: "Analytics", path: "/dashboard/analytics" },
    { name: "Risk", path: "/dashboard/risk" },
  ];

  return (
    <div className="flex h-screen bg-gray-900">
      {/* Sidebar */}
      <aside className="w-64 bg-gray-800 border-r border-gray-700">
        <div className="p-6">
          <h1 className="text-2xl font-bold text-yellow-400">🐝 Hive</h1>
          <p className="text-sm text-gray-400">Trading System</p>
        </div>
        <nav className="mt-6">
          {navItems.map((item) => (
            <Link
              key={item.path}
              href={item.path}
              className={`block px-6 py-3 text-sm font-medium transition-colors ${
                pathname === item.path
                  ? "bg-gray-700 text-yellow-400 border-l-4 border-yellow-400"
                  : "text-gray-300 hover:bg-gray-700 hover:text-white"
              }`}
            >
              {item.name}
            </Link>
          ))}
        </nav>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <div className="p-8">{children}</div>
      </main>
    </div>
  );
}
