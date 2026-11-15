FROM node:22-alpine AS build
WORKDIR /app
COPY dashboard/package*.json ./
RUN npm ci
COPY dashboard/ .
ARG VITE_SENTINELOPS_API_URL
ARG VITE_PAYFLOW_API_URL
RUN npm run build
FROM nginxinc/nginx-unprivileged:stable-alpine
COPY infrastructure/docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
