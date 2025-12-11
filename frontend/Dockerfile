FROM node:20-alpine AS build
WORKDIR /app

ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

# 先装依赖，使用 npm ci 保证可重复构建
COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 4173

HEALTHCHECK --interval=30s --timeout=10s --retries=3 CMD wget -qO- http://localhost:4173/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
