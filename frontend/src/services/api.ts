import axios from 'axios';
import type {
  DailyPerformanceItem,
  DrawdownResponse,
  FearGreedResponse,
  ForwardPeResponse,
  MarketBreadthResponse,
  MarketSummary,
  RelativeSeries,
  RelativeToResponse,
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

export const fetchDrawdown = async (
  symbol: string,
  range = '1Y',
): Promise<DrawdownResponse> => {
  const { data } = await api.get<DrawdownResponse>('/api/performance/drawdown', {
    params: { symbol, range },
  });
  return data;
};

export const fetchRelativeTo = async (
  symbol: string,
  benchmark: string,
  range = '1Y',
): Promise<RelativeToResponse> => {
  const { data } = await api.get<RelativeToResponse>('/api/performance/relative-to', {
    params: { symbol, benchmark, range },
  });
  return data;
};

export const fetchFearGreedComparison = async (
  range = '1Y',
): Promise<FearGreedResponse> => {
  const { data } = await api.get<FearGreedResponse>('/api/market/fear-greed', {
    params: { range },
  });
  return data;
};

export const fetchForwardPeComparison = async (
  range = '1Y',
): Promise<ForwardPeResponse> => {
  const { data } = await api.get<ForwardPeResponse>('/api/market/forward-pe', {
    params: { range },
  });
  return data;
};

export const fetchMarketBreadth = async (
  symbols: string[],
  range = '1M',
  benchmark = '^NDX',
): Promise<MarketBreadthResponse> => {
  const { data } = await api.get<MarketBreadthResponse>('/api/market/breadth', {
    params: { symbols: symbols.join(','), range, benchmark },
  });
  return data;
};

export const clearApiCache = async (): Promise<void> => {
  await api.post('/api/cache/clear');
};
