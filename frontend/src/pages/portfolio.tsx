import { type ColumnDef } from "@tanstack/react-table";
import { DataTable } from "@/components/ui/data-table";
import { useAppStore } from "@/stores/app-store";
import type { OpenPosition } from "@/lib/api-types";
import { fmtPLN, fmtDate, fmtQty } from "@/lib/format";
import { numericSort } from "@/lib/sorting";

const columns: ColumnDef<OpenPosition, unknown>[] = [
  { accessorKey: "symbol", header: "Symbol" },
  { accessorKey: "remaining_quantity", header: "Ilość", sortingFn: numericSort, cell: ({ getValue }) => fmtQty(getValue() as string) },
  { accessorKey: "price_per_unit", header: "Cena (avg)", sortingFn: numericSort, cell: ({ getValue }) => fmtPLN(getValue() as string, 4) },
  { accessorKey: "currency", header: "Waluta", size: 60 },
  { accessorKey: "trade_date", header: "Data kupna", cell: ({ getValue }) => fmtDate(getValue() as string) },
  { accessorKey: "settle_date", header: "Data rozliczenia", cell: ({ getValue }) => fmtDate(getValue() as string | null) },
];

export function PortfolioPage() {
  const result = useAppStore((s) => s.result);

  if (!result) {
    return <p className="text-muted-foreground">Najpierw zaimportuj dane.</p>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Portfolio</h2>
        <p className="text-muted-foreground">
          {result.open_positions.length} otwartych pozycji
        </p>
      </div>

      {result.open_positions.length > 0 ? (
        <DataTable columns={columns} data={result.open_positions} />
      ) : (
        <p className="text-muted-foreground">Brak otwartych pozycji.</p>
      )}
    </div>
  );
}
