# ---- Build ----
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .
RUN npm run build

# ---- Serve ----
FROM nginx:alpine AS runner
COPY --from=builder /app/dist /usr/share/nginx/html
# Redirige toutes les routes SPA vers index.html + proxifie /api → backend
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
