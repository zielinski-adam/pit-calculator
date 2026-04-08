/** Hook do kalkulacji PIT-38 (TanStack Query mutation). */

import { useMutation } from "@tanstack/react-query";
import { calculatePit38 } from "@/lib/api-client";
import { useAppStore } from "@/stores/app-store";

export function useCalculate() {
  const { setResult, setIsCalculating, setError } = useAppStore();

  return useMutation({
    mutationFn: ({
      files,
      taxYear,
      priorLosses,
    }: {
      files: File[];
      taxYear: number;
      priorLosses: string;
    }) => calculatePit38(files, taxYear, priorLosses),

    onMutate: () => {
      setIsCalculating(true);
      setError(null);
    },

    onSuccess: (data) => {
      setResult(data);
      setIsCalculating(false);
    },

    onError: (error) => {
      setError(error instanceof Error ? error.message : "Nieznany błąd");
      setIsCalculating(false);
    },
  });
}
