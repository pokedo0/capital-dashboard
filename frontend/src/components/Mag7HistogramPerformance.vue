<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue';
import * as echarts from 'echarts';
import { useQuery } from '@tanstack/vue-query';
import TimeRangeSelector from './TimeRangeSelector.vue';
import { fetchRelativePerformance } from '../services/api';

const BASE_SYMBOLS = ['NVDA', 'GOOG', 'AMZN', 'AAPL', 'META', 'MSFT', 'TSLA', '^NDX'] as const;
const EXTENDED_SYMBOLS = [...BASE_SYMBOLS, 'AVGO', 'TSM'] as const;
type SymbolKey = (typeof EXTENDED_SYMBOLS)[number];
const BASELINE_SYMBOL = '^NDX';
const SYMBOL_LABELS: Record<SymbolKey, string> = {
  '^NDX': 'NDX',
  NVDA: 'NVDA',
  GOOG: 'GOOG',
  AMZN: 'AMZN',
  AAPL: 'AAPL',
  META: 'META',
  MSFT: 'MSFT',
  TSLA: 'TSLA',
  AVGO: 'AVGO',
  TSM: 'TSM',
};
const isTrackedSymbol = (value: string): value is SymbolKey =>
  (EXTENDED_SYMBOLS as readonly string[]).includes(value as SymbolKey);
const MS_PER_DAY = 24 * 60 * 60 * 1000;
const downsampleWeekly = (points: { time: string; value: number }[]) => {
  if (!points.length) return points;
  const result: typeof points = [];
  let lastSampleTime: number | null = null;
  points.forEach((point) => {
    const current = new Date(point.time).getTime();
    if (Number.isNaN(current)) {
      result.push(point);
      return;
    }
    if (lastSampleTime === null || current - lastSampleTime >= 7 * MS_PER_DAY) {
      result.push(point);
      lastSampleTime = current;
    } else {
      result[result.length - 1] = point;
    }
  });
  return result;
};
const rangeOptions = ['1W', '1M', '3M', 'YTD', '1Y', '5Y'];

const rangeKey = ref('1W');
const lineupMode = ref<'M7' | 'M9'>('M7');
const displayedSymbols = computed(() =>
  lineupMode.value === 'M7' ? BASE_SYMBOLS : EXTENDED_SYMBOLS,
);
const chartRef = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;

const queryRange = computed(() => (rangeKey.value === 'YTD' ? '1Y' : rangeKey.value));

const { data, refetch } = useQuery({
  queryKey: computed(() => ['relative', 'mag7-group', rangeKey.value]),
  queryFn: () => fetchRelativePerformance([...EXTENDED_SYMBOLS], rangeKey.value),
});

watch(rangeKey, () => refetch());

const seriesData = computed(() => {
  if (!data.value) return [];
  const cutoff = new Date(new Date().getFullYear(), 0, 1);
  const allowed = new Set(displayedSymbols.value);
  return data.value
    .map((series) => {
      let points = series.points;
      if (rangeKey.value === 'YTD') {
        points = points.filter((point) => new Date(point.time) >= cutoff);
      } else if (rangeKey.value === '5Y') {
        points = downsampleWeekly(points);
      }
      if (!points.length) return null;
      const first = points[0];
      const last = points[points.length - 1];
      if (!first || !last || typeof first.value !== 'number' || typeof last.value !== 'number') {
        return null;
      }
      if (!isTrackedSymbol(series.symbol) || !allowed.has(series.symbol)) return null;
      const change = last.value - first.value;
      return { symbol: series.symbol, change, label: SYMBOL_LABELS[series.symbol] ?? series.symbol };
    })
    .filter((item): item is { symbol: SymbolKey; change: number; label: string } => !!item)
    .sort((a, b) => b.change - a.change);
});

const renderChart = () => {
  if (!chartRef.value) return;
  if (!chart) {
    chart = echarts.init(chartRef.value);
    window.addEventListener('resize', resizeChart);
  }
  const payload = seriesData.value;
    const isMobile = window.innerWidth < 768;
    const option = {
      grid: {
        left: isMobile ? 10 : 50,
        right: isMobile ? 10 : 40,
        top: 30,
        bottom: 40,
        containLabel: true,
      },
      xAxis: {      type: 'category',
      data: payload.map((item) => item.label),
      axisLabel: { color: '#f8fafc', margin: 10, interval: 0 },
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.2)' } },
    },
    yAxis: {
      type: 'value',
      axisLabel: { formatter: '{value}%', color: '#f8fafc' },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      valueFormatter: (value: number) => `${value.toFixed(2)}%`,
    },
    series: [
      {
        type: 'bar',
        data: payload.map((item) => {
          const isBaseline = item.symbol === BASELINE_SYMBOL;
          const color = isBaseline ? '#f5f5f5' : item.change >= 0 ? '#22c55e' : '#ef4444';
          return {
            value: item.change,
            itemStyle: {
              color,
              borderColor: isBaseline ? '#38bdf8' : undefined,
              borderWidth: isBaseline ? 1.5 : 0,
            },
            label: {
              show: true,
              position: item.change >= 0 ? 'top' : 'insideBottom',
              formatter: `${item.change.toFixed(2)}%`,
              color: isBaseline ? '#38bdf8' : '#f8fafc',
              fontSize: 11,
              fontWeight: isBaseline ? '600' : 'normal',
              distance: 4,
            },
          };
        }),
      },
    ],
  };
  chart.setOption(option, true);
};

const resizeChart = () => {
  chart?.resize();
};

watch(seriesData, () => {
  renderChart();
});

onMounted(() => {
  renderChart();
});

onBeforeUnmount(() => {
  if (chart) {
    window.removeEventListener('resize', resizeChart);
    chart.dispose();
    chart = null;
  }
});
</script>

<template>
  <div class="bg-panel border border-white/10 rounded-xl p-2 md:p-4 flex flex-col gap-4 h-full w-full">
    <div class="flex flex-wrap justify-between items-center gap-4">
      <div>
        <div class="text-xl text-accentCyan font-semibold uppercase">Mag 7 Histogram Performance</div>
      </div>
      <div class="flex items-center gap-3">
        <div class="flex bg-white/10 rounded-full overflow-hidden text-xs font-medium text-white">
          <button
            type="button"
            class="px-3 py-1 transition-colors"
            :class="lineupMode === 'M7' ? 'bg-accentCyan text-black' : 'text-white/70'"
            @click="lineupMode = 'M7'"
          >
            M7
          </button>
          <button
            type="button"
            class="px-3 py-1 transition-colors"
            :class="lineupMode === 'M9' ? 'bg-accentCyan text-black' : 'text-white/70'"
            @click="lineupMode = 'M9'"
          >
            M9
          </button>
        </div>
        <TimeRangeSelector v-model="rangeKey" :options="rangeOptions" />
      </div>
    </div>
    <div ref="chartRef" class="w-full flex-1 aspect-[4/3] md:aspect-auto md:min-h-[420px]"></div>
  </div>
</template>
