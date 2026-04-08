import { useState, useMemo } from "react";
import { type ColumnDef } from "@tanstack/react-table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataTable } from "@/components/ui/data-table";
import { Button } from "@/components/ui/button";
import { useAppStore } from "@/stores/app-store";
import type { TaxLot } from "@/lib/api-types";
import { fmtPLN, fmtDate, fmtQty, plClass } from "@/lib/format";
import { numericSort } from "@/lib/sorting";
import { InfoTooltip } from "@/components/ui/info-tooltip";
import { ChevronDown, ChevronRight } from "lucide-react";

const columns: ColumnDef<TaxLot, unknown>[] = [
  { accessorKey: "buy_trade_date", header: "Kupno (trade)", cell: ({ getValue }) => fmtDate(getValue() as string) },
  { accessorKey: "buy_settle_date", header: "Kupno (settle)", cell: ({ getValue }) => fmtDate(getValue() as string) },
  { accessorKey: "buy_price", header: "Cena kupna", sortingFn: numericSort, cell: ({ getValue }) => fmtPLN(getValue() as string, 4) },
  { accessorKey: "buy_quantity", header: "Ilość", sortingFn: numericSort, cell: ({ getValue }) => fmtQty(getValue() as string) },
  { accessorKey: "buy_nbp_rate", header: "NBP kupno", sortingFn: numericSort, cell: ({ getValue }) => fmtPLN(getValue() as string, 4) },
  { accessorKey: "buy_cost_pln", header: "Koszt (PLN)", sortingFn: numericSort, cell: ({ getValue }) => fmtPLN(getValue() as string) },
  { accessorKey: "sell_trade_date", header: "Sprzedaż (trade)", cell: ({ getValue }) => fmtDate(getValue() as string) },
  { accessorKey: "sell_settle_date", header: "Sprzedaż (settle)", cell: ({ getValue }) => fmtDate(getValue() as string) },
  { accessorKey: "sell_price", header: "Cena sprzedaży", sortingFn: numericSort, cell: ({ getValue }) => fmtPLN(getValue() as string, 4) },
  { accessorKey: "sell_nbp_rate", header: "NBP sprzedaż", sortingFn: numericSort, cell: ({ getValue }) => fmtPLN(getValue() as string, 4) },
  { accessorKey: "sell_proceeds_pln", header: "Przychód (PLN)", sortingFn: numericSort, cell: ({ getValue }) => fmtPLN(getValue() as string) },
  {
    accessorKey: "profit_loss_pln",
    header: "Zysk/Strata (PLN)",
    sortingFn: numericSort,
    cell: ({ getValue }) => {
      const v = getValue() as string;
      return <span className={plClass(v)}>{fmtPLN(v)}</span>;
    },
  },
];

interface SymbolGroup {
  symbol: string;
  country: string;
  currency: string;
  listing_exchange: string;
  asset_category: string;
  lots: TaxLot[];
  totalProceeds: number;
  totalCosts: number;
  totalProfitLoss: number;
}

function groupBySymbol(lots: TaxLot[]): SymbolGroup[] {
  const map = new Map<string, TaxLot[]>();
  for (const lot of lots) {
    const existing = map.get(lot.symbol);
    if (existing) {
      existing.push(lot);
    } else {
      map.set(lot.symbol, [lot]);
    }
  }

  return Array.from(map.entries()).map(([symbol, groupLots]) => {
    const first = groupLots[0]!;
    return {
      symbol,
      country: first.country,
      currency: first.currency,
      listing_exchange: first.listing_exchange,
      asset_category: first.asset_category,
      lots: groupLots,
      totalProceeds: groupLots.reduce((s, l) => s + Number(l.sell_proceeds_pln), 0),
      totalCosts: groupLots.reduce((s, l) => s + Number(l.buy_cost_pln), 0),
      totalProfitLoss: groupLots.reduce((s, l) => s + Number(l.profit_loss_pln), 0),
    };
  });
}

export function FifoPage() {
  const result = useAppStore((s) => s.result);
  const [allOpen, setAllOpen] = useState(false);

  const groups = useMemo(
    () => (result ? groupBySymbol(result.tax_lots) : []),
    [result]
  );

  if (!result) {
    return <p className="text-muted-foreground">Najpierw zaimportuj dane.</p>;
  }

  return (
    <div className="space-y-6">
      <h2 className="text-3xl font-bold tracking-tight">FIFO</h2>

      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Zamknięte pozycje
              <InfoTooltip text="Liczba pozycji rozliczonych metodą FIFO w danym roku podatkowym." ariaLabel="Informacja o zamkniętych pozycjach" />
            </CardTitle>
          </CardHeader>
          <CardContent><p className="text-2xl font-bold">{result.tax_lots_count}</p></CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Przychody (C.22)
              <InfoTooltip text="Suma przychodów ze sprzedaży papierów wartościowych — pole C.22 formularza PIT-38." ariaLabel="Informacja o polu C.22" />
            </CardTitle>
          </CardHeader>
          <CardContent><p className="text-2xl font-bold">{fmtPLN(result.c22_proceeds)} PLN</p></CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Koszty (C.23)
              <InfoTooltip text="Suma kosztów uzyskania przychodów (cena kupna + prowizje) — pole C.23 formularza PIT-38." ariaLabel="Informacja o polu C.23" />
            </CardTitle>
          </CardHeader>
          <CardContent><p className="text-2xl font-bold">{fmtPLN(result.c23_costs)} PLN</p></CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              {Number(result.c28_income) > 0 ? "Dochód (C.28)" : "Strata (C.29)"}
              <InfoTooltip text="Różnica między przychodami a kosztami. Dochód: pole C.28, Strata: pole C.29 formularza PIT-38." ariaLabel="Informacja o dochodzie/stracie" />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className={`text-2xl font-bold ${plClass(result.c28_income > result.c29_loss ? result.c28_income : `-${result.c29_loss}`)}`}>
              {Number(result.c28_income) > 0
                ? `${fmtPLN(result.c28_income)} PLN`
                : `-${fmtPLN(result.c29_loss)} PLN`}
            </p>
          </CardContent>
        </Card>
      </div>

      {result.warnings.length > 0 && (
        <Card className="border-yellow-500">
          <CardHeader>
            <CardTitle className="text-sm text-yellow-600">Ostrzeżenia ({result.warnings.length})</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-1 text-sm">
              {result.warnings.map((w, i) => <li key={i} className="text-muted-foreground">{w}</li>)}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Kontrolki akordeonu */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">{groups.length} symboli, {result.tax_lots_count} pozycji</p>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setAllOpen((v) => !v)}
        >
          {allOpen ? "Zwiń wszystkie" : "Rozwiń wszystkie"}
        </Button>
      </div>

      {/* Grupy akordeonowe */}
      <div className="space-y-3">
        {groups.map((group) => (
          <SymbolAccordionControlled
            key={group.symbol}
            group={group}
            forceOpen={allOpen}
          />
        ))}
      </div>
    </div>
  );
}

/** Akordeon z obsługą "rozwiń/zwiń wszystkie" */
function SymbolAccordionControlled({ group, forceOpen }: { group: SymbolGroup; forceOpen: boolean }) {
  const [manualOpen, setManualOpen] = useState<boolean | null>(null);
  const isOpen = manualOpen ?? forceOpen;

  return (
    <div className="rounded-md border">
      <button
        type="button"
        className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-muted/50 transition-colors"
        onClick={() => setManualOpen(isOpen ? false : true)}
        aria-expanded={isOpen}
      >
        <div className="flex items-center gap-4">
          {isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          <span className="font-bold text-lg">{group.symbol}</span>
          <span className="text-xs text-muted-foreground">{group.asset_category}</span>
          <span className="text-xs text-muted-foreground">{group.listing_exchange}</span>
          <span className="text-xs text-muted-foreground">{group.country}</span>
          <span className="text-xs text-muted-foreground">{group.currency}</span>
          <span className="text-xs text-muted-foreground">{group.lots.length} poz.</span>
        </div>
        <div className="flex items-center gap-6 text-sm">
          <span>Przychód: <strong>{fmtPLN(group.totalProceeds)}</strong></span>
          <span>Koszt: <strong>{fmtPLN(group.totalCosts)}</strong></span>
          <span className={plClass(group.totalProfitLoss)}>
            Wynik: <strong>{fmtPLN(group.totalProfitLoss)}</strong>
          </span>
        </div>
      </button>

      {isOpen && (
        <div className="border-t px-2 pb-2">
          <DataTable columns={columns} data={group.lots} pageSize={50} />
          <div className="flex justify-end gap-6 px-3 py-2 text-sm font-semibold border-t bg-muted/30">
            <span>Przychód: {fmtPLN(group.totalProceeds)}</span>
            <span>Koszt: {fmtPLN(group.totalCosts)}</span>
            <span className={plClass(group.totalProfitLoss)}>
              Wynik: {fmtPLN(group.totalProfitLoss)}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
