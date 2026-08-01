FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .

# Vite inlines VITE_* env at BUILD time. Without this the bundle falls back to
# the localhost default in src/api/client.js and the deployed app calls the
# user's own machine. Pass the API's public URL via --build-arg VITE_API_URL=...
# (docker-compose.prod.yml wires this from the .env VITE_API_URL).
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
