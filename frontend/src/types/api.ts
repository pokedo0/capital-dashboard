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

export interface MarketSummary {
  market: string;
  date: string;
  index_value: number;
  day_change: number;
  day_change_pct: number;
  vix_value: number;
  vix_change_pct: number;
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
