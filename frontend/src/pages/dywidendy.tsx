import { type ColumnDef } from "@tanstack/react-table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataTable } from "@/components/ui/data-table";
import { Badge } from "@/components/ui/badge";
import { useAppStore } from "@/stores/app-store";
import type { DividendEntry, WhtEntry } from "@/lib/api-types";
import { fmtPLN, fmtDate } from "@/lib/format";

const divColumns: ColumnDef<DividendEntry, unknown>[] = [
  { accessorKey: "symbol", header: "Symbol" },
  { accessorKey: "isin", header: "ISIN" },
  { accessorKey: "payment_date", header: "Data", cell: ({ getValue }) => fmtDate(getValue() as string) },
  { accessorKey: "amount", header: "Kwota", cell: ({ getValue }) => fmtPLN(getValue() as string) },
  { accessorKey: "currency", header: "Waluta", size: 60 },
  { accessorKey: "dividend_type", header: "Typ", cell: ({ getValue }) => {
    const v = getValue() as string;
    return (
      <Badge variant={v === "PAYMENT_IN_LIEU" ? "destructive" : "secondary"}>
        {v === "CASH_DIVIDEND" ? "Cash" : "PIL"}
      </Badge>
    );
  }},
];

const whtColumns: ColumnDef<WhtEntry, unknown>[] = [
  { accessorKey: "symbol", header: "Symbol", cell: ({ getValue }) => (getValue() as string | null) ?? "—" },
  { accessorKey: "payment_date", header: "Data", cell: ({ getValue }) => fmtDate(getValue() as string) },
  { accessorKey: "amount", header: "Kwota", cell: ({ getValue }) => fmtPLN(getValue() as string) },
  { accessorKey: "currency", header: "Waluta", size: 60 },
  { accessorKey: "wht_type", header: "Typ", cell: ({ getValue }) => {
    const v = getValue() as string;
    return (
      <Badge variant={v === "DIVIDEND_WHT" ? "default" : "outline"}>
        {v === "DIVIDEND_WHT" ? "Dywidenda" : "Odsetki"}
      </Badge>
    );
  }},
];

export function DywidendyPage() {
  const result = useAppStore((s) => s.result);

  if (!result) {
    return <p className="text-muted-foreground">Najpierw zaimportuj dane.</p>;
  }

  return (
    <div className="space-y-6">
      <h2 className="text-3xl font-bold tracking-tight">Dywidendy</h2>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Dywidendy brutto (PLN)</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{fmtPLN(result.dividends_gross_pln)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">WHT zapłacony (G.48)</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{fmtPLN(result.g48_dividend_wht)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Do dopłaty (G.49)</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{fmtPLN(result.g49_dividend_difference, 0)} PLN</p>
          </CardContent>
        </Card>
      </div>

      <div>
        <h3 className="mb-3 text-xl font-semibold">Dywidendy ({result.dividends.length})</h3>
        <DataTable columns={divColumns} data={result.dividends} />
      </div>

      {result.withholding_taxes.length > 0 && (
        <div>
          <h3 className="mb-3 text-xl font-semibold">Withholding Tax ({result.withholding_taxes.length})</h3>
          <DataTable columns={whtColumns} data={result.withholding_taxes} />
        </div>
      )}
    </div>
  );
}
