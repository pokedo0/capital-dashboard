<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue';
import * as echarts from 'echarts';
import { useQuery } from '@tanstack/vue-query';
import TimeRangeSelector from './TimeRangeSelector.vue';
import { fetchRelativePerformance } from '../services/api';

const SYMBOLS = ['NVDA', 'GOOG', 'AMZN', 'AAPL', 'META', 'MSFT', 'TSLA', '^NDX', 'AVGO'] as const;
const SYMBOL_LABELS: Record<(typeof SYMBOLS)[number], string> = {
  '^NDX': 'NDX',
  NVDA: 'NVDA',
  GOOG: 'GOOG',
  AMZN: 'AMZN',
  AAPL: 'AAPL',
  META: 'META',
  MSFT: 'MSFT',
  TSLA: 'TSLA',
  AVGO: 'AVGO',
};
const isTrackedSymbol = (value: string): value is (typeof SYMBOLS)[number] =>
  (SYMBOLS as readonly string[]).includes(value as (typeof SYMBOLS)[number]);
const rangeOptions = ['1W', '1M', '3M', 'YTD', '1Y'];

const rangeKey = ref('1W');
const chartRef = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;

const queryRange = computed(() => (rangeKey.value === 'YTD' ? '1Y' : rangeKey.value));

const { data, refetch } = useQuery({
  queryKey: computed(() => ['mag7-histogram', rangeKey.value]),
  queryFn: () => fetchRelativePerformance([...SYMBOLS], queryRange.value),
});

watch(rangeKey, () => refetch());

const seriesData = computed(() => {
  if (!data.value) return [];
  const cutoff = new Date(new Date().getFullYear(), 0, 1);
  return data.value
    .map((series) => {
      let points = series.points;
      if (rangeKey.value === 'YTD') {
        points = points.filter((point) => new Date(point.time) >= cutoff);
      }
      if (!points.length) return null;
      const first = points[0];
      const last = points[points.length - 1];
      if (!first || !last || typeof first.value !== 'number' || typeof last.value !== 'number') {
        return null;
      }
      if (!isTrackedSymbol(series.symbol)) return null;
      const change = last.value - first.value;
      return { symbol: series.symbol, change, label: SYMBOL_LABELS[series.symbol] ?? series.symbol };
    })
    .filter(
      (item): item is { symbol: (typeof SYMBOLS)[number]; change: number; label: string } => !!item,
    )
    .sort((a, b) => b.change - a.change);
});

const renderChart = () => {
  if (!chartRef.value) return;
  if (!chart) {
    chart = echarts.init(chartRef.value);
    window.addEventListener('resize', resizeChart);
  }
  const payload = seriesData.value;
  const option = {
    grid: { left: 50, right: 40, top: 30, bottom: 40, containLabel: true },
    xAxis: {
      type: 'category',
      data: payload.map((item) => item.label),
      axisLabel: { color: '#f8fafc', margin: 10 },
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
        data: payload.map((item) => ({
          value: item.change,
          itemStyle: { color: item.change >= 0 ? '#22c55e' : '#ef4444' },
          label: {
            show: true,
            position: item.change >= 0 ? 'top' : 'insideBottom',
            formatter: `${item.change.toFixed(2)}%`,
            color: '#f8fafc',
            fontSize: 11,
            distance: 4,
          },
        })),
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
  <div class="bg-panel border border-white/10 rounded-xl p-4 flex flex-col gap-4 h-full">
    <div class="flex flex-wrap justify-between items-center gap-4">
      <div>
        <div class="text-xl text-accentCyan font-semibold uppercase">Mag 7 Histogram Performance</div>
      </div>
      <TimeRangeSelector v-model="rangeKey" :options="rangeOptions" />
    </div>
    <div ref="chartRef" class="w-full flex-1 min-h-[420px]"></div>
  </div>
</template>
