import { useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, FileText, Loader2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAppStore } from "@/stores/app-store";
import { useCalculate } from "@/hooks/use-calculate";

export function ImportPage() {
  const { files, setFiles, taxYear, setTaxYear, priorLosses, setPriorLosses, isCalculating, error, result } =
    useAppStore();
  const calculate = useCalculate();

  const onDrop = useCallback(
    (accepted: File[]) => {
      if (accepted.length > 0) {
        setFiles([...files, ...accepted]);
      }
    },
    [files, setFiles]
  );

  const removeFile = useCallback(
    (index: number) => {
      setFiles(files.filter((_, i) => i !== index));
    },
    [files, setFiles]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "text/csv": [".csv"] },
  });

  const handleCalculate = () => {
    if (files.length === 0) return;
    calculate.mutate({ files, taxYear, priorLosses });
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Import</h2>
        <p className="text-muted-foreground">
          Wgraj IBKR Activity Statement CSV
        </p>
      </div>

      {/* Dropzone */}
      <Card>
        <CardContent className="pt-6">
          <div
            {...getRootProps()}
            className={`flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 transition-colors ${
              isDragActive
                ? "border-primary bg-primary/5"
                : "border-muted-foreground/25 hover:border-primary/50"
            }`}
          >
            <input {...getInputProps()} />
            <Upload className="mb-3 h-10 w-10 text-muted-foreground" />
            <p className="font-medium">Przeciągnij pliki CSV lub kliknij</p>
            <p className="text-sm text-muted-foreground">
              IBKR Activity Statement (format CSV) -- możesz dodać kilka plików
            </p>
          </div>

          {files.length > 0 && (
            <div className="mt-4 space-y-2">
              {files.map((f, i) => (
                <div
                  key={`${f.name}-${i}`}
                  className="flex items-center justify-between rounded-md border px-3 py-2"
                >
                  <div className="flex items-center gap-2">
                    <FileText className="h-4 w-4 text-primary" />
                    <span className="text-sm font-medium">{f.name}</span>
                    <span className="text-xs text-muted-foreground">
                      {(f.size / 1024).toFixed(1)} KB
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      removeFile(i);
                    }}
                    className="rounded-sm p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Parametry */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Parametry</CardTitle>
          <CardDescription>Rok podatkowy i straty z lat ubiegłych</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium" htmlFor="tax-year">
                Rok podatkowy
              </label>
              <input
                id="tax-year"
                type="number"
                min={2020}
                max={2030}
                value={taxYear}
                onChange={(e) => setTaxYear(Number(e.target.value))}
                className="mt-1 flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="text-sm font-medium" htmlFor="prior-losses">
                Straty z lat ubiegłych (D.30)
              </label>
              <input
                id="prior-losses"
                type="text"
                value={priorLosses}
                onChange={(e) => setPriorLosses(e.target.value)}
                placeholder="0"
                className="mt-1 flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              />
            </div>
          </div>

          <Button
            onClick={handleCalculate}
            disabled={files.length === 0 || isCalculating}
            className="w-full"
            size="lg"
          >
            {isCalculating ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Obliczanie...
              </>
            ) : (
              "Oblicz PIT-38"
            )}
          </Button>
        </CardContent>
      </Card>

      {/* Błąd */}
      {error && (
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <p className="text-sm text-destructive">{error}</p>
          </CardContent>
        </Card>
      )}

      {/* Sukces */}
      {result && (
        <Card className="border-green-500">
          <CardContent className="pt-6 text-center">
            <p className="text-lg font-semibold text-green-600">
              Kalkulacja zakończona
            </p>
            <p className="text-sm text-muted-foreground">
              {result.trades_count} transakcji, {result.tax_lots_count} pozycji
              FIFO, {result.dividends_count} dywidend
            </p>
            <p className="mt-2 text-2xl font-bold">
              Podatek: {Number(result.total_tax_due).toLocaleString("pl-PL")} PLN
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
