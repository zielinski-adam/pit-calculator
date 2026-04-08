import { useMemo, useState } from "react";
import { type ColumnDef } from "@tanstack/react-table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DataTable } from "@/components/ui/data-table";
import { Badge } from "@/components/ui/badge";
import { useAppStore } from "@/stores/app-store";
import type { DividendEntry, WhtEntry } from "@/lib/api-types";
import { fmtPLN, fmtDate } from "@/lib/format";
import { numericSort } from "@/lib/sorting";
import { InfoTooltip } from "@/components/ui/info-tooltip";

const divColumns: ColumnDef<DividendEntry, unknown>[] = [
  { accessorKey: "symbol", header: "Symbol" },
  { accessorKey: "isin", header: "ISIN" },
  { accessorKey: "payment_date", header: "Data", cell: ({ getValue }) => fmtDate(getValue() as string) },
  { accessorKey: "amount", header: "Kwota (PLN)", sortingFn: numericSort, cell: ({ getValue }) => fmtPLN(getValue() as string) },
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
  { accessorKey: "amount", header: "Kwota (PLN)", sortingFn: numericSort, cell: ({ getValue }) => fmtPLN(getValue() as string) },
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

interface SymbolSummary {
  symbol: string;
  count: number;
  totalAmount: number;
  totalWht: number;
  net: number;
}

function buildSymbolSummaries(dividends: DividendEntry[], wht: WhtEntry[]): SymbolSummary[] {
  const map = new Map<string, SymbolSummary>();

  for (const d of dividends) {
    const key = d.symbol || d.description;
    const existing = map.get(key);
    if (existing) {
      existing.count += 1;
      existing.totalAmount += Number(d.amount);
    } else {
      map.set(key, { symbol: key, count: 1, totalAmount: Number(d.amount), totalWht: 0, net: 0 });
    }
  }

  for (const w of wht) {
    const key = w.symbol || w.description;
    const existing = map.get(key);
    if (existing) {
      existing.totalWht += Math.abs(Number(w.amount));
    } else {
      map.set(key, { symbol: key, count: 0, totalAmount: 0, totalWht: Math.abs(Number(w.amount)), net: 0 });
    }
  }

  const result = Array.from(map.values());
  for (const s of result) {
    s.net = s.totalAmount - s.totalWht;
  }
  return result.sort((a, b) => b.totalAmount - a.totalAmount);
}

const symbolColumns: ColumnDef<SymbolSummary, unknown>[] = [
  { accessorKey: "symbol", header: "Symbol" },
  { accessorKey: "count", header: "Wypłaty", sortingFn: numericSort },
  { accessorKey: "totalAmount", header: "Suma przychodów", sortingFn: numericSort, cell: ({ getValue }) => fmtPLN(getValue() as number) },
  { accessorKey: "totalWht", header: "Suma podatków", sortingFn: numericSort, cell: ({ getValue }) => fmtPLN(getValue() as number) },
  { accessorKey: "net", header: "Dochód netto", sortingFn: numericSort, cell: ({ getValue }) => fmtPLN(getValue() as number) },
];

export function DywidendyPage() {
  const result = useAppStore((s) => s.result);
  const [search, setSearch] = useState("");

  const symbolSummaries = useMemo(
    () => (result ? buildSymbolSummaries(result.dividends, result.withholding_taxes) : []),
    [result]
  );

  const filteredDividends = useMemo(() => {
    if (!result || !search) return result?.dividends ?? [];
    const q = search.toLowerCase();
    return result.dividends.filter(
      (d) => d.symbol.toLowerCase().includes(q) || d.isin.toLowerCase().includes(q) || d.description.toLowerCase().includes(q)
    );
  }, [result, search]);

  const filteredWht = useMemo(() => {
    if (!result || !search) return result?.withholding_taxes ?? [];
    const q = search.toLowerCase();
    return result.withholding_taxes.filter(
      (w) => (w.symbol?.toLowerCase().includes(q)) || (w.isin?.toLowerCase().includes(q)) || w.description.toLowerCase().includes(q)
    );
  }, [result, search]);

  if (!result) {
    return <p className="text-muted-foreground">Najpierw zaimportuj dane.</p>;
  }

  return (
    <div className="space-y-6">
      <h2 className="text-3xl font-bold tracking-tight">Dywidendy</h2>

      {/* Karty podsumowania */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Dywidendy brutto
              <InfoTooltip text="Suma brutto otrzymanych dywidend i odsetek przeliczonych na PLN." ariaLabel="Informacja o dywidendach brutto" />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{fmtPLN(result.dividends_gross_pln)} PLN</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Podatek 19% (G.47)
              <InfoTooltip text="Podatek należny od dywidend: 19% od kwoty brutto — pole G.47 formularza PIT-38." ariaLabel="Informacja o polu G.47" />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{fmtPLN(result.g47_dividend_tax)} PLN</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              WHT zapłacony (G.48)
              <InfoTooltip text="Podatek u źródła (Withholding Tax) zapłacony za granicą — pole G.48 formularza PIT-38. Odlicza się od podatku należnego." ariaLabel="Informacja o polu G.48" />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{fmtPLN(result.g48_dividend_wht)} PLN</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Do dopłaty (G.49)
              <InfoTooltip text="Różnica między podatkiem należnym (19%) a zapłaconym WHT — pole G.49. Kwota zaokrąglona do pełnych złotych." ariaLabel="Informacja o polu G.49" />
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{fmtPLN(result.g49_dividend_difference, 0)} PLN</p>
          </CardContent>
        </Card>
      </div>

      {/* Wyszukiwarka */}
      <div>
        <input
          type="text"
          placeholder="Wyszukaj po symbolu, ISIN lub opisie..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full max-w-md rounded-md border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          aria-label="Wyszukaj dywidendy"
        />
      </div>

      {/* Tabela dywidend */}
      <div>
        <h3 className="mb-3 text-xl font-semibold">Dywidendy ({filteredDividends.length})</h3>
        <DataTable columns={divColumns} data={filteredDividends} />
      </div>

      {/* Tabela WHT */}
      {filteredWht.length > 0 && (
        <div>
          <h3 className="mb-3 text-xl font-semibold">Withholding Tax ({filteredWht.length})</h3>
          <DataTable columns={whtColumns} data={filteredWht} />
        </div>
      )}

      {/* Zestawienie informacyjne */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Zestawienie informacyjne</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm max-w-lg">
            <span className="text-muted-foreground">Otrzymane wypłaty</span>
            <span className="font-medium text-right">{result.dividends.length}</span>
            <span className="text-muted-foreground">Suma przychodów</span>
            <span className="font-medium text-right">{fmtPLN(result.dividends_gross_pln)} zł</span>
            <span className="text-muted-foreground">Podatek do dopłaty</span>
            <span className="font-medium text-right">{fmtPLN(result.dividend_topup_exact)} zł</span>
            <span className="text-muted-foreground">Podatek do dopłaty (zaokrąglony)</span>
            <span className="font-bold text-right">{fmtPLN(result.g49_dividend_difference, 0)} zł</span>
          </div>
        </CardContent>
      </Card>

      {/* Zestawienie symboli */}
      {symbolSummaries.length > 0 && (
        <div>
          <h3 className="mb-3 text-xl font-semibold">Zestawienie symboli</h3>
          <p className="mb-2 text-sm text-muted-foreground">Suma wypłat według symbolu</p>
          <DataTable columns={symbolColumns} data={symbolSummaries} />
        </div>
      )}
    </div>
  );
}
