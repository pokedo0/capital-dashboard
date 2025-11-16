import { onBeforeUnmount, onMounted, ref } from 'vue';
import { createChart, type DeepPartial, type IChartApi, type LayoutOptions } from 'lightweight-charts';

export function useLightweightChart(options: DeepPartial<LayoutOptions> & Record<string, unknown> = {}) {
  const containerRef = ref<HTMLDivElement | null>(null);
  const chartRef = ref<IChartApi | null>(null);

  onMounted(() => {
    if (!containerRef.value) return;
    chartRef.value = createChart(containerRef.value, {
      layout: {
        background: { color: '#050505' },
        textColor: '#f5f5f5',
        fontFamily: "'IBM Plex Sans', Inter, ui-sans-serif, system-ui",
      },
      grid: {
        vertLines: { color: 'rgba(255,255,255,0.05)' },
        horzLines: { color: 'rgba(255,255,255,0.05)' },
      },
      localization: { priceFormatter: (price: number) => price.toFixed(2) },
      ...options,
    });

    const resizeObserver = new ResizeObserver(() => {
      if (containerRef.value && chartRef.value) {
        chartRef.value.applyOptions({
          width: containerRef.value.clientWidth,
          height: containerRef.value.clientHeight,
        });
      }
    });
    resizeObserver.observe(containerRef.value);
    (chartRef.value as unknown as { resizeObserver?: ResizeObserver }).resizeObserver = resizeObserver;
  });

  onBeforeUnmount(() => {
    const chart = chartRef.value;
    const resizeObserver = (chart as unknown as { resizeObserver?: ResizeObserver })?.resizeObserver;
    resizeObserver?.disconnect();
    chart?.remove();
    chartRef.value = null;
  });

  return { containerRef, chartRef };
}
