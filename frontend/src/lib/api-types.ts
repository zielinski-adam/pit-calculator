/** Typy odpowiadające backendu (api/schemas.py). */

export interface PitZgEntry {
  country_code: string;
  country_name: string;
  capital_gains_income: string;
  other_income: string;
  foreign_tax_paid: string;
}

export interface TaxLot {
  symbol: string;
  isin: string;
  country: string;
  listing_exchange: string;
  asset_category: string;
  currency: string;
  multiplier: number;

  buy_trade_date: string;
  buy_settle_date: string;
  buy_nbp_rate_date: string;
  buy_nbp_rate: string;
  buy_price: string;
  buy_quantity: string;
  buy_commission: string;
  buy_cost_pln: string;

  sell_trade_date: string;
  sell_settle_date: string;
  sell_nbp_rate_date: string;
  sell_nbp_rate: string;
  sell_price: string;
  sell_quantity: string;
  sell_commission: string;
  sell_proceeds_pln: string;

  profit_loss_pln: string;
}

export interface Trade {
  symbol: string;
  isin: string;
  asset_category: string;
  currency: string;
  listing_exchange: string;
  trade_date: string;
  settle_date: string | null;
  quantity: string;
  price: string;
  proceeds: string;
  commission: string;
  multiplier: number;
  codes: string[];
}

export interface DividendEntry {
  symbol: string;
  isin: string;
  currency: string;
  payment_date: string;
  amount: string;
  dividend_type: string;
  description: string;
}

export interface WhtEntry {
  symbol: string | null;
  isin: string | null;
  currency: string;
  payment_date: string;
  amount: string;
  wht_type: string;
  description: string;
}

export interface CorporateActionEntry {
  symbol: string;
  isin: string;
  action_date: string;
  action_type: string;
  description: string;
  quantity: string;
  ratio_from: number | null;
  ratio_to: number | null;
}

export interface OpenPosition {
  symbol: string;
  remaining_quantity: string;
  price_per_unit: string;
  trade_date: string;
  settle_date: string | null;
  currency: string;
}

export interface CalculateResponse {
  tax_year: number;

  // Sekcja C
  c22_proceeds: string;
  c23_costs: string;
  c26_total_proceeds: string;
  c27_total_costs: string;
  c28_income: string;
  c29_loss: string;

  // Sekcja D
  d30_prior_losses: string;
  d31_tax_base: string;
  d32_tax_rate: number;
  d33_tax_calculated: string;
  d34_foreign_tax: string;
  d35_tax_due: string;

  // Sekcja G
  dividends_gross_pln: string;
  g47_dividend_tax: string;
  g48_dividend_wht: string;
  dividend_topup_exact: string;
  g49_dividend_difference: string;

  // PIT/ZG
  pit_zg_entries: PitZgEntry[];

  // Suma
  total_tax_due: string;

  // Dane szczegółowe
  tax_lots: TaxLot[];
  trades: Trade[];
  dividends: DividendEntry[];
  withholding_taxes: WhtEntry[];
  corporate_actions: CorporateActionEntry[];
  open_positions: OpenPosition[];

  // Meta
  trades_count: number;
  tax_lots_count: number;
  dividends_count: number;
  warnings: string[];
}

export interface HealthResponse {
  status: string;
  version: string;
}

export interface ErrorResponse {
  detail: string;
}
