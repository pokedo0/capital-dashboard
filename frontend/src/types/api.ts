export interface OHLCVPoint {
  time: string;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  close?: number | null;
  volume?: number | null;
}

export interface SeriesPayload {
  symbol: string;
  points: OHLCVPoint[];
}

export interface RelativePoint {
  time: string;
  value: number;
}

export interface RelativeSeries {
  symbol: string;
  points: RelativePoint[];
}

export interface MarketBreadthResponse {
  benchmark_percent: RelativeSeries;
  benchmark_price: ValuePoint[];
  series: RelativeSeries[];
}

export interface MarketSummary {
  market: string;
  date: string;
  index_value: number;
  day_change: number;
  day_change_pct: number;
  vix_value: number;
  vix_change_pct: number;
  advancers_pct?: number;
  decliners_pct?: number;
}

export interface SectorItem {
  name: string;
  symbol: string;
  change_pct: number;
  volume_millions: number;
  percent_of_avg: number;
}

export interface SectorSummaryResponse {
  sectors: SectorItem[];
}

export interface DailyPerformanceItem {
  symbol: string;
  change_pct: number;
  latest_close: number;
}

export interface ValuePoint {
  time: string;
  value: number;
}

export interface DrawdownResponse {
  symbol: string;
  drawdown: ValuePoint[];
  price: ValuePoint[];
  current_drawdown: number;
  max_drawdown: number;
}

export interface RelativeToResponse {
  symbol: string;
  benchmark: string;
  ratio: ValuePoint[];
  moving_average: ValuePoint[];
}

export interface FearGreedResponse {
  index: ValuePoint[];
  spy: ValuePoint[];
}

export interface ForwardPeResponse {
  forward_pe: ValuePoint[];
  spx: ValuePoint[];
}

export interface SpyRspRatioResponse {
  ratio: ValuePoint[];
  mags: ValuePoint[];
}
