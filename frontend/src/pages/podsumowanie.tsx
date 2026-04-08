import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { useAppStore } from "@/stores/app-store";

function Row({ label, value, bold }: { label: string; value: string; bold?: boolean }) {
  return (
    <div className="flex items-center justify-between py-1">
      <span className={bold ? "font-semibold" : "text-muted-foreground"}>{label}</span>
      <span className={bold ? "text-lg font-bold" : "font-mono"}>{value}</span>
    </div>
  );
}

function fmt(v: string, decimals = 2): string {
  return Number(v).toLocaleString("pl-PL", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function PodsumowaniePage() {
  const result = useAppStore((s) => s.result);

  if (!result) {
    return <p className="text-muted-foreground">Najpierw zaimportuj dane.</p>;
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h2 className="text-3xl font-bold tracking-tight">
        Podsumowanie PIT-38 za {result.tax_year}
      </h2>

      {/* Sekcja C */}
      <Card>
        <CardHeader>
          <CardTitle>Sekcja C -- Przychody z odpłatnego zbycia</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1">
          <Row label="C.22 Przychody" value={`${fmt(result.c22_proceeds)} PLN`} />
          <Row label="C.23 Koszty uzyskania" value={`${fmt(result.c23_costs)} PLN`} />
          <Separator className="my-2" />
          <Row label="C.26 Razem przychody" value={`${fmt(result.c26_total_proceeds)} PLN`} />
          <Row label="C.27 Razem koszty" value={`${fmt(result.c27_total_costs)} PLN`} />
          <Separator className="my-2" />
          <Row label="C.28 Dochód" value={`${fmt(result.c28_income)} PLN`} bold />
          <Row label="C.29 Strata" value={`${fmt(result.c29_loss)} PLN`} />
        </CardContent>
      </Card>

      {/* Sekcja D */}
      <Card>
        <CardHeader>
          <CardTitle>Sekcja D -- Obliczenie podatku</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1">
          <Row label="D.30 Straty z lat ubiegłych" value={`${fmt(result.d30_prior_losses)} PLN`} />
          <Row label="D.31 Podstawa obliczenia" value={`${fmt(result.d31_tax_base, 0)} PLN`} />
          <Row label="D.32 Stawka" value={`${result.d32_tax_rate}%`} />
          <Row label="D.33 Podatek obliczony" value={`${fmt(result.d33_tax_calculated)} PLN`} />
          <Row label="D.34 Podatek zagraniczny" value={`${fmt(result.d34_foreign_tax)} PLN`} />
          <Separator className="my-2" />
          <Row label="D.35 Podatek należny" value={`${fmt(result.d35_tax_due, 0)} PLN`} bold />
        </CardContent>
      </Card>

      {/* Sekcja G */}
      <Card>
        <CardHeader>
          <CardTitle>Sekcja G -- Dywidendy zagraniczne</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1">
          <Row label="Dywidendy brutto" value={`${fmt(result.dividends_gross_pln)} PLN`} />
          <Row label="G.47 Podatek 19%" value={`${fmt(result.g47_dividend_tax)} PLN`} />
          <Row label="G.48 WHT zapłacony" value={`${fmt(result.g48_dividend_wht)} PLN`} />
          <Separator className="my-2" />
          <Row label="G.49 Do dopłaty" value={`${fmt(result.g49_dividend_difference, 0)} PLN`} bold />
        </CardContent>
      </Card>

      {/* PIT/ZG */}
      {result.pit_zg_entries.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>PIT/ZG -- per kraj</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {result.pit_zg_entries.map((e) => (
                <div key={e.country_code} className="flex items-center justify-between">
                  <span>
                    {e.country_name} ({e.country_code})
                  </span>
                  <span className="font-mono">
                    {fmt(e.capital_gains_income)} PLN
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Suma */}
      <Card className="border-green-500 bg-green-50">
        <CardContent className="pt-6 text-center">
          <p className="text-sm text-muted-foreground">Łączny podatek do zapłaty</p>
          <p className="text-4xl font-bold text-green-700">
            {fmt(result.total_tax_due, 0)} PLN
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            D.35 ({fmt(result.d35_tax_due, 0)}) + G.49 ({fmt(result.g49_dividend_difference, 0)})
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
