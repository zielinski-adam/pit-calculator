import { type ColumnDef } from "@tanstack/react-table";
import { DataTable } from "@/components/ui/data-table";
import { useAppStore } from "@/stores/app-store";
import type { CorporateActionEntry } from "@/lib/api-types";
import { fmtDate, fmtQty } from "@/lib/format";
import { numericSort } from "@/lib/sorting";

const columns: ColumnDef<CorporateActionEntry, unknown>[] = [
  { accessorKey: "symbol", header: "Symbol" },
  { accessorKey: "isin", header: "ISIN" },
  { accessorKey: "action_date", header: "Data", cell: ({ getValue }) => fmtDate(getValue() as string) },
  { accessorKey: "action_type", header: "Typ" },
  {
    id: "ratio",
    header: "Proporcja",
    cell: ({ row }) => {
      const from = row.original.ratio_from;
      const to = row.original.ratio_to;
      return from && to ? `${to}:${from}` : "—";
    },
  },
  { accessorKey: "quantity", header: "Zmiana ilości", sortingFn: numericSort, cell: ({ getValue }) => fmtQty(getValue() as string) },
  { accessorKey: "description", header: "Opis" },
];

export function SplityPage() {
  const result = useAppStore((s) => s.result);

  if (!result) {
    return <p className="text-muted-foreground">Najpierw zaimportuj dane.</p>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Splity</h2>
        <p className="text-muted-foreground">
          {result.corporate_actions.length} corporate actions
        </p>
      </div>

      {result.corporate_actions.length > 0 ? (
        <DataTable columns={columns} data={result.corporate_actions} />
      ) : (
        <p className="text-muted-foreground">Brak zdarzeń korporacyjnych.</p>
      )}
    </div>
  );
}
