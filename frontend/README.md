# Capital Dashboard Frontend

Vue 3 + Vite + Tailwind 的单页应用，展示市场概览、回撤、相对表现、多资产等图表。

## 本地开发

```bash
cd frontend
npm install
npm run dev -- --host
```

接口地址通过 `.env` 配置，默认 `VITE_API_BASE_URL=http://localhost:8000/api`。

## 构建与预览

```bash
npm run build
npm run preview
```

## 主要依赖

- Vue 3 + TypeScript
- Vite 7
- Tailwind CSS
- lightweight-charts、ECharts（部分组件）
