# Base images are pinned by digest, not just by tag: `node:20-alpine` is a moving
# target that silently changes content between builds, so a build that passed CI
# is not the build that ships. Refresh these deliberately (docker pull the tag,
# read off the new digest) rather than drifting by accident.
FROM node:20-alpine@sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293 AS builder

WORKDIR /app

COPY package.json package-lock.json* ./
# `npm ci` (not `npm install`) — installs exactly the locked tree and fails if
# package.json and the lockfile disagree, so a build can't quietly resolve a
# different dependency version than the one CI audited.
RUN npm ci

COPY . .

# Vite inlines VITE_* env at BUILD time. Without this the bundle falls back to
# the localhost default in src/api/client.js and the deployed app calls the
# user's own machine. Pass the API's public URL via --build-arg VITE_API_URL=...
# (docker-compose.prod.yml wires this from the .env VITE_API_URL).
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:1.29-alpine@sha256:5616878291a2eed594aee8db4dade5878cf7edcb475e59193904b198d9b830de

ARG VITE_API_URL

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY security-headers.conf /etc/nginx/snippets/security-headers.conf

# Bake the API origin into the CSP's connect-src. The scheme+host+port is taken
# from VITE_API_URL (the same value compiled into the bundle) so the policy and
# the code it governs can never disagree. Any path component is stripped — CSP
# source expressions match on origin.
RUN set -eu; \
    origin=$(printf '%s' "${VITE_API_URL:-}" | sed -E 's#^(https?://[^/]+).*#\1#'); \
    sed -i "s#__CSP_CONNECT_SRC__#${origin}#" /etc/nginx/snippets/security-headers.conf

# Run unprivileged. The stock nginx image runs its master as root purely so it
# can bind :80; the server block listens on 8080 instead, which needs no
# privilege. Drop the `user` directive (meaningless once the master is already
# unprivileged, and it logs a warning every start) and move the pidfile somewhere
# the nginx user can actually write.
RUN sed -i 's#^user .*#\# master already runs unprivileged; user directive removed#' /etc/nginx/nginx.conf \
    && sed -i 's#/var/run/nginx.pid#/tmp/nginx.pid#' /etc/nginx/nginx.conf \
    && chown -R nginx:nginx /var/cache/nginx /usr/share/nginx/html \
    && nginx -t

USER nginx

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://127.0.0.1:8080/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
