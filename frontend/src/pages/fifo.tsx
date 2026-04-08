import { type ColumnDef } from "@tanstack/react-table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataTable } from "@/components/ui/data-table";
import { useAppStore } from "@/stores/app-store";
import type { TaxLot } from "@/lib/api-types";
import { fmtPLN, fmtDate, fmtQty, plClass } from "@/lib/format";

const columns: ColumnDef<TaxLot, unknown>[] = [
  { accessorKey: "symbol", header: "Symbol", size: 100 },
  { accessorKey: "buy_trade_date", header: "Kupno (trade)", cell: ({ getValue }) => fmtDate(getValue() as string) },
  { accessorKey: "buy_settle_date", header: "Kupno (settle)", cell: ({ getValue }) => fmtDate(getValue() as string) },
  { accessorKey: "buy_price", header: "Cena kupna", cell: ({ getValue }) => fmtPLN(getValue() as string, 4) },
  { accessorKey: "buy_quantity", header: "Ilość", cell: ({ getValue }) => fmtQty(getValue() as string) },
  { accessorKey: "buy_nbp_rate", header: "NBP kupno", cell: ({ getValue }) => fmtPLN(getValue() as string, 4) },
  { accessorKey: "buy_cost_pln", header: "Koszt (PLN)", cell: ({ getValue }) => fmtPLN(getValue() as string) },
  { accessorKey: "sell_trade_date", header: "Sprzedaż (trade)", cell: ({ getValue }) => fmtDate(getValue() as string) },
  { accessorKey: "sell_settle_date", header: "Sprzedaż (settle)", cell: ({ getValue }) => fmtDate(getValue() as string) },
  { accessorKey: "sell_price", header: "Cena sprzedaży", cell: ({ getValue }) => fmtPLN(getValue() as string, 4) },
  { accessorKey: "sell_nbp_rate", header: "NBP sprzedaż", cell: ({ getValue }) => fmtPLN(getValue() as string, 4) },
  { accessorKey: "sell_proceeds_pln", header: "Przychód (PLN)", cell: ({ getValue }) => fmtPLN(getValue() as string) },
  {
    accessorKey: "profit_loss_pln",
    header: "Zysk/Strata (PLN)",
    cell: ({ getValue }) => {
      const v = getValue() as string;
      return <span className={plClass(v)}>{fmtPLN(v)}</span>;
    },
  },
  { accessorKey: "currency", header: "Waluta", size: 60 },
  { accessorKey: "country", header: "Kraj", size: 50 },
];

export function FifoPage() {
  const result = useAppStore((s) => s.result);

  if (!result) {
    return <p className="text-muted-foreground">Najpierw zaimportuj dane.</p>;
  }

  return (
    <div className="space-y-6">
      <h2 className="text-3xl font-bold tracking-tight">FIFO</h2>

      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Zamknięte pozycje</CardTitle>
          </CardHeader>
          <CardContent><p className="text-2xl font-bold">{result.tax_lots_count}</p></CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Przychody (C.22)</CardTitle>
          </CardHeader>
          <CardContent><p className="text-2xl font-bold">{fmtPLN(result.c22_proceeds)} PLN</p></CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Koszty (C.23)</CardTitle>
          </CardHeader>
          <CardContent><p className="text-2xl font-bold">{fmtPLN(result.c23_costs)} PLN</p></CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              {Number(result.c28_income) > 0 ? "Dochód (C.28)" : "Strata (C.29)"}
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

      <DataTable columns={columns} data={result.tax_lots} />
    </div>
  );
}
