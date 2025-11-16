import axios from 'axios';
import type {
  DailyPerformanceItem,
  MarketSummary,
  RelativeSeries,
  SectorSummaryResponse,
  SeriesPayload,
} from '../types/api';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000',
});

export const fetchOhlcv = async (symbol: string, range = '1Y'): Promise<SeriesPayload> => {
  const { data } = await api.get<SeriesPayload>('/api/ohlcv', { params: { symbol, range } });
  return data;
};

export const fetchRelativePerformance = async (
  symbols: string[],
  range = '1M',
): Promise<RelativeSeries[]> => {
  const { data } = await api.get<RelativeSeries[]>('/api/performance/relative', {
    params: { symbols: symbols.join(','), range },
  });
  return data;
};

export const fetchMarketSummary = async (market: string): Promise<MarketSummary> => {
  const { data } = await api.get<MarketSummary>('/api/market/summary', { params: { market } });
  return data;
};

export const fetchSectorSummary = async (): Promise<SectorSummaryResponse> => {
  const { data } = await api.get<SectorSummaryResponse>('/api/sectors/summary');
  return data;
};

export const fetchDailyPerformance = async (symbols: string[]): Promise<DailyPerformanceItem[]> => {
  const { data } = await api.get<DailyPerformanceItem[]>('/api/performance/daily', {
    params: { symbols: symbols.join(',') },
  });
  return data;
};
