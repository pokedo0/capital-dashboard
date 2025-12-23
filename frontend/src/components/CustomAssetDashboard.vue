<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';
import TimeRangeSelector from './TimeRangeSelector.vue';
import CustomRelativeChart from './CustomRelativeChart.vue';
import CustomHistogramChart from './CustomHistogramChart.vue';

// Configuration
const DEFAULT_SYMBOLS = ['NVDA', 'NVDL', 'NVDY'];
const STORAGE_KEY = 'custom-comparison-symbols';
const PALETTE = [
  '#2563eb', // Blue
  '#16a34a', // Green
  '#dc2626', // Red
  '#d97706', // Amber
  '#9333ea', // Purple
  '#0891b2', // Cyan
  '#db2777', // Pink
  '#ea580c', // Orange
];

// State
const symbols = ref<string[]>([]);
const hiddenSymbols = ref<Set<string>>(new Set());
const inputSymbol = ref('');
const rangeKey = ref('1M');
const rangeOptions = ['1W', '1M', '3M', '6M', 'YTD', '1Y', '3Y'];

// Initialize from local storage or default
onMounted(() => {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored) {
    try {
      const parsed = JSON.parse(stored);
      if (Array.isArray(parsed) && parsed.length > 0) {
        symbols.value = parsed;
      } else {
        symbols.value = [...DEFAULT_SYMBOLS];
      }
    } catch {
      symbols.value = [...DEFAULT_SYMBOLS];
    }
  } else {
    symbols.value = [...DEFAULT_SYMBOLS];
  }
});

// Persistence
watch(symbols, (newVal) => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(newVal));
  // Clean up hidden symbols that are no longer in the list
  const currentSet = new Set(newVal);
  for (const hidden of hiddenSymbols.value) {
    if (!currentSet.has(hidden)) {
      hiddenSymbols.value.delete(hidden);
    }
  }
}, { deep: true });

// Actions
const addSymbol = () => {
  const val = inputSymbol.value.trim().toUpperCase();
  if (!val) return;
  if (symbols.value.includes(val)) {
    inputSymbol.value = '';
    return;
  }
  if (symbols.value.length >= 8) {
    alert('Maximum 8 symbols allowed');
    return;
  }
  symbols.value.push(val);
  inputSymbol.value = '';
};

const removeSymbol = (symbol: string) => {
  if (symbols.value.length <= 1) {
    alert('At least 1 symbol required');
    return;
  }
  symbols.value = symbols.value.filter(s => s !== symbol);
  hiddenSymbols.value.delete(symbol);
};

const toggleVisibility = (symbol: string) => {
  if (hiddenSymbols.value.has(symbol)) {
    hiddenSymbols.value.delete(symbol);
  } else {
    hiddenSymbols.value.add(symbol);
  }
};

const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter') {
    addSymbol();
  }
};
</script>

<template>
  <div class="bg-panel border border-white/10 rounded-xl p-4 flex flex-col gap-4 w-full">
    <!-- Header -->
    <div class="flex flex-wrap justify-between items-center gap-4">
      <div class="text-xl font-semibold uppercase" style="color: #67f0d6">Custom Asset Comparison</div>
      
      <div class="flex flex-wrap items-center gap-3">
        <!-- Add Symbol Input -->
        <div class="flex items-center gap-2 bg-black/20 border border-white/10 rounded px-2 py-1">
          <input
            v-model="inputSymbol"
            type="text"
            placeholder="ADD SYMBOL"
            class="bg-transparent border-none outline-none text-white w-20 text-xs uppercase placeholder-white/30"
            @keydown="handleKeydown"
          />
          <button
            @click="addSymbol"
            class="text-accentCyan hover:text-white transition-colors"
            :disabled="symbols.length >= 8"
            title="Add Symbol"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clip-rule="evenodd" />
            </svg>
          </button>
        </div>
        <TimeRangeSelector v-model="rangeKey" :options="rangeOptions" />
      </div>
    </div>

    <!-- Active Tags -->
    <div class="flex flex-wrap gap-2">
      <div
        v-for="(sym, idx) in symbols"
        :key="sym"
        class="flex items-center gap-1.5 px-2 py-0.5 rounded border text-[10px] font-medium transition-all cursor-pointer select-none"
        :class="hiddenSymbols.has(sym) 
          ? 'bg-transparent border-white/5 text-white/30' 
          : 'bg-white/5 border-white/10 text-white hover:bg-white/10'"
        @click="toggleVisibility(sym)"
      >
        <span 
          class="w-1.5 h-1.5 rounded-full transition-colors" 
          :style="{ backgroundColor: hiddenSymbols.has(sym) ? '#444' : PALETTE[idx % PALETTE.length] }"
        ></span>
        <span>{{ sym }}</span>
        <button
          @click.stop="removeSymbol(sym)"
          class="ml-1 hover:text-red-400 transition-colors"
          :class="hiddenSymbols.has(sym) ? 'text-white/20' : 'text-white/40'"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
          </svg>
        </button>
      </div>
    </div>

    <!-- Charts Layout -->
    <div class="grid gap-4 w-full xl:grid-cols-[3fr,1fr]">
      <div class="min-h-[360px] flex flex-col">
        <CustomRelativeChart :symbols="symbols" :hidden-symbols="hiddenSymbols" :range="rangeKey" :colors="PALETTE" />
      </div>
      <div class="min-h-[360px] flex flex-col">
        <CustomHistogramChart :symbols="symbols" :hidden-symbols="hiddenSymbols" :range="rangeKey" :colors="PALETTE" />
      </div>
    </div>
  </div>
</template>
