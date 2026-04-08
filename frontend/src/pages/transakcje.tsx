import { type ColumnDef } from "@tanstack/react-table";
import { DataTable } from "@/components/ui/data-table";
import { Badge } from "@/components/ui/badge";
import { useAppStore } from "@/stores/app-store";
import type { Trade } from "@/lib/api-types";
import { fmtPLN, fmtDate, fmtQty } from "@/lib/format";
import { numericSort } from "@/lib/sorting";

const columns: ColumnDef<Trade, unknown>[] = [
  { accessorKey: "symbol", header: "Symbol" },
  { accessorKey: "asset_category", header: "Kategoria", cell: ({ getValue }) => {
    const v = getValue() as string;
    return v === "Stocks" ? "Akcje" : v === "Equity and Index Options" ? "Opcje" : v === "Treasury Bills" ? "Bony skarbowe" : v;
  }},
  { accessorKey: "trade_date", header: "Data transakcji", cell: ({ getValue }) => fmtDate(getValue() as string) },
  { accessorKey: "settle_date", header: "Data rozliczenia", cell: ({ getValue }) => fmtDate(getValue() as string | null) },
  { accessorKey: "quantity", header: "Ilość", sortingFn: numericSort, cell: ({ getValue }) => {
    const q = Number(getValue() as string);
    return <span className={q > 0 ? "text-green-600" : "text-red-600"}>{fmtQty(getValue() as string)}</span>;
  }},
  { accessorKey: "price", header: "Cena", sortingFn: numericSort, cell: ({ getValue }) => fmtPLN(getValue() as string, 4) },
  { accessorKey: "proceeds", header: "Kwota", sortingFn: numericSort, cell: ({ getValue }) => fmtPLN(getValue() as string) },
  { accessorKey: "commission", header: "Prowizja", sortingFn: numericSort, cell: ({ getValue }) => fmtPLN(getValue() as string) },
  { accessorKey: "currency", header: "Waluta", size: 60 },
  { accessorKey: "listing_exchange", header: "Giełda", size: 80 },
  { accessorKey: "codes", header: "Kod", cell: ({ getValue }) => {
    const codes = getValue() as string[];
    return codes.map((c) => (
      <Badge key={c} variant={c === "O" ? "secondary" : c === "C" ? "default" : "outline"} className="mr-1">
        {c === "O" ? "Open" : c === "C" ? "Close" : c}
      </Badge>
    ));
  }},
];

export function TransakcjePage() {
  const result = useAppStore((s) => s.result);

  if (!result) {
    return <p className="text-muted-foreground">Najpierw zaimportuj dane.</p>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Transakcje</h2>
        <p className="text-muted-foreground">
          {result.trades_count} transakcji w roku {result.tax_year}
        </p>
      </div>

      <DataTable columns={columns} data={result.trades} />
    </div>
  );
}
