/** Globalny store aplikacji (Zustand). */

import { create } from "zustand";
import type { CalculateResponse } from "@/lib/api-types";

interface AppState {
  // Pliki CSV (IBKR pozwala max 365 dni -- użytkownik może wgrać kilka)
  files: File[];
  setFiles: (files: File[]) => void;

  // Parametry kalkulacji
  taxYear: number;
  setTaxYear: (year: number) => void;
  priorLosses: string;
  setPriorLosses: (losses: string) => void;

  // Wynik kalkulacji
  result: CalculateResponse | null;
  setResult: (result: CalculateResponse | null) => void;

  // Stan UI
  isCalculating: boolean;
  setIsCalculating: (v: boolean) => void;
  error: string | null;
  setError: (error: string | null) => void;

  // Reset
  reset: () => void;
}

const currentYear = new Date().getFullYear() - 1; // Domyślnie poprzedni rok

export const useAppStore = create<AppState>((set) => ({
  files: [],
  setFiles: (files) => set({ files, result: null, error: null }),

  taxYear: currentYear,
  setTaxYear: (taxYear) => set({ taxYear }),

  priorLosses: "0",
  setPriorLosses: (priorLosses) => set({ priorLosses }),

  result: null,
  setResult: (result) => set({ result }),

  isCalculating: false,
  setIsCalculating: (isCalculating) => set({ isCalculating }),

  error: null,
  setError: (error) => set({ error }),

  reset: () =>
    set({
      files: [],
      result: null,
      error: null,
      isCalculating: false,
      priorLosses: "0",
    }),
}));
