export interface PendingBuy {
  symbol: string;
  planned_capital: number;
  decision_date: string;
}

export interface Position {
  symbol: string;
  entry_price: number;
  shares: number;
  entry_date: string;
  days_held: number;
}

export interface PortfolioState {
  cash: number;
  positions: Position[];
  pending_buys: PendingBuy[];
  last_date: string;
}

export interface EquityPoint {
  date: string;
  value: number;
}
