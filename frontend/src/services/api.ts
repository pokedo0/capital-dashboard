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

const rawBaseUrl = (import.meta.env.VITE_API_BASE_URL || '').trim();
const baseCandidate = rawBaseUrl || '/api';
const sanitizedBase = baseCandidate.replace(/\/+$/, '');
const basePath =
  (() => {
    try {
      return new URL(sanitizedBase, 'http://placeholder').pathname;
    } catch {
      return sanitizedBase;
    }
  })() || sanitizedBase;
// Guarantee calls always hit the backend /api prefix even if the env var omits it.
const baseWithApi = /\/api(\/|$)/.test(basePath) ? sanitizedBase : `${sanitizedBase}/api`;
const baseURL = `${baseWithApi.replace(/\/+$/, '')}/`;

const api = axios.create({ baseURL });

export const fetchOhlcv = async (symbol: string, range = '1Y'): Promise<SeriesPayload> => {
  const { data } = await api.get<SeriesPayload>('ohlcv', { params: { symbol, range } });
  return data;
};

export const fetchRelativePerformance = async (
  symbols: string[],
  range = '1M',
): Promise<RelativeSeries[]> => {
  const { data } = await api.get<RelativeSeries[]>('performance/relative', {
    params: { symbols: symbols.join(','), range },
  });
  return data;
};

export const fetchMarketSummary = async (market: string): Promise<MarketSummary> => {
  const { data } = await api.get<MarketSummary>('market/summary', { params: { market } });
  return data;
};

export const fetchSectorSummary = async (): Promise<SectorSummaryResponse> => {
  const { data } = await api.get<SectorSummaryResponse>('sectors/summary');
  return data;
};

export const fetchDailyPerformance = async (symbols: string[]): Promise<DailyPerformanceItem[]> => {
  const { data } = await api.get<DailyPerformanceItem[]>('performance/daily', {
    params: { symbols: symbols.join(',') },
  });
  return data;
};

export const fetchDrawdown = async (
  symbol: string,
  range = '1Y',
): Promise<DrawdownResponse> => {
  const { data } = await api.get<DrawdownResponse>('performance/drawdown', {
    params: { symbol, range },
  });
  return data;
};

export const fetchRelativeTo = async (
  symbol: string,
  benchmark: string,
  range = '1Y',
): Promise<RelativeToResponse> => {
  const { data } = await api.get<RelativeToResponse>('performance/relative-to', {
    params: { symbol, benchmark, range },
  });
  return data;
};

export const fetchFearGreedComparison = async (
  range = '1Y',
): Promise<FearGreedResponse> => {
  const { data } = await api.get<FearGreedResponse>('market/fear-greed', {
    params: { range },
  });
  return data;
};

export const fetchForwardPeComparison = async (
  range = '1Y',
): Promise<ForwardPeResponse> => {
  const { data } = await api.get<ForwardPeResponse>('market/forward-pe', {
    params: { range },
  });
  return data;
};

export const fetchMarketBreadth = async (
  symbols: string[],
  range = '1M',
  benchmark = '^NDX',
): Promise<MarketBreadthResponse> => {
  const { data } = await api.get<MarketBreadthResponse>('market/breadth', {
    params: { symbols: symbols.join(','), range, benchmark },
  });
  return data;
};

// ============ Realtime APIs (5-minute TTL) ============

export const fetchRealtimeMarketSummary = async (market: string): Promise<MarketSummary> => {
  const { data } = await api.get<MarketSummary>('market/realtime-summary', { params: { market } });
  return data;
};

export const fetchRealtimeSectorSummary = async (): Promise<SectorSummaryResponse> => {
  const { data } = await api.get<SectorSummaryResponse>('sectors/realtime-summary');
  return data;
};

export const clearApiCache = async (): Promise<void> => {
  await api.post('cache/clear');
};

