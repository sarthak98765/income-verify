FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
# Vite inlines this at build time. Empty = call /api, which nginx proxies.
ARG VITE_BACKEND_URL=""
ARG VITE_TURNSTILE_SITE_KEY=""
ENV VITE_BACKEND_URL=$VITE_BACKEND_URL VITE_TURNSTILE_SITE_KEY=$VITE_TURNSTILE_SITE_KEY
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
