import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { useAppStore } from "@/stores/app-store";
import { fmtPLN } from "@/lib/format";

export function KosztyPage() {
  const result = useAppStore((s) => s.result);

  if (!result) {
    return <p className="text-muted-foreground">Najpierw zaimportuj dane.</p>;
  }

  // Oblicz sumy prowizji z tax_lots
  const buyCommissions = result.tax_lots.reduce(
    (sum, lot) => sum + Math.abs(Number(lot.buy_commission)),
    0
  );
  const sellCommissions = result.tax_lots.reduce(
    (sum, lot) => sum + Math.abs(Number(lot.sell_commission)),
    0
  );
  const totalCommissions = buyCommissions + sellCommissions;

  // Suma prowizji z transakcji (pełna lista)
  const tradeCommissions = result.trades.reduce(
    (sum, t) => sum + Math.abs(Number(t.commission)),
    0
  );

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h2 className="text-3xl font-bold tracking-tight">Koszty</h2>

      <Card>
        <CardHeader>
          <CardTitle>Prowizje maklerskie</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Prowizje kupna (w tax lots)</span>
            <span className="font-mono">{fmtPLN(buyCommissions)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Prowizje sprzedaży (w tax lots)</span>
            <span className="font-mono">{fmtPLN(sellCommissions)}</span>
          </div>
          <Separator />
          <div className="flex justify-between font-semibold">
            <span>Razem prowizje (zamknięte pozycje)</span>
            <span>{fmtPLN(totalCommissions)}</span>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Prowizje z wszystkich transakcji</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Suma prowizji (wszystkie transakcje)</span>
            <span className="font-mono">{fmtPLN(tradeCommissions)}</span>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            Uwaga: prowizje w PLN są obliczane per-leg (z kursem NBP D-1 od settlement date).
            Powyższa suma jest w walucie oryginalnej (przed przeliczeniem).
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Podsumowanie kosztów PIT-38</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="flex justify-between">
            <span className="text-muted-foreground">C.23 Koszty uzyskania przychodu (PLN)</span>
            <span className="font-mono">{fmtPLN(result.c23_costs)}</span>
          </div>
          <p className="text-xs text-muted-foreground">
            Zawiera: koszt nabycia + prowizje kupna (przeliczone na PLN per NBP rate z D-1 settlement date).
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
