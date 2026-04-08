import { Link, useMatchRoute } from "@tanstack/react-router";
import {
  Upload,
  Layers,
  ArrowLeftRight,
  Split,
  Briefcase,
  Coins,
  Receipt,
  FileText,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/stores/app-store";

const navItems = [
  { to: "/", label: "Import", icon: Upload },
  { to: "/fifo", label: "FIFO", icon: Layers },
  { to: "/transakcje", label: "Transakcje", icon: ArrowLeftRight },
  { to: "/splity", label: "Splity", icon: Split },
  { to: "/portfolio", label: "Portfolio", icon: Briefcase },
  { to: "/dywidendy", label: "Dywidendy", icon: Coins },
  { to: "/koszty", label: "Koszty", icon: Receipt },
  { to: "/podsumowanie", label: "Podsumowanie", icon: FileText },
] as const;

export function Sidebar() {
  const matchRoute = useMatchRoute();
  const result = useAppStore((s) => s.result);

  return (
    <aside className="flex h-full w-56 flex-col border-r bg-card">
      <div className="p-4">
        <h1 className="text-lg font-bold">PIT-38</h1>
        <p className="text-xs text-muted-foreground">Kalkulator IBKR</p>
      </div>

      <nav className="flex-1 space-y-1 px-2">
        {navItems.map(({ to, label, icon: Icon }) => {
          const isActive = matchRoute({ to, fuzzy: to !== "/" });
          const isDisabled = to !== "/" && !result;

          return (
            <Link
              key={to}
              to={to}
              disabled={isDisabled}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : isDisabled
                    ? "cursor-not-allowed text-muted-foreground/50"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
      </nav>

      {result && (
        <div className="border-t p-4">
          <p className="text-xs text-muted-foreground">Rok: {result.tax_year}</p>
          <p className="text-xs text-muted-foreground">
            Transakcje: {result.trades_count}
          </p>
        </div>
      )}
    </aside>
  );
}
