import { type SortingFn } from "@tanstack/react-table";

/** Sortowanie numeryczne dla kolumn z wartościami Decimal (stringi z backendu). */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const numericSort: SortingFn<any> = (rowA, rowB, columnId) => {
  return Number(rowA.getValue(columnId)) - Number(rowB.getValue(columnId));
};
