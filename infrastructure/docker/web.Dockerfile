FROM node:24-bookworm-slim AS dependencies

ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /app
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci

FROM node:24-bookworm-slim AS builder

ARG API_INTERNAL_URL=http://api:8000
ENV API_INTERNAL_URL=${API_INTERNAL_URL}
ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /app
COPY --from=dependencies /app/node_modules ./node_modules
COPY apps/web ./
# Keep the compiler in a separate worker and bound its heap on small Docker Desktop VMs.
# Type checking remains enabled; this limit applies only to the build stage.
ARG WEB_BUILD_HEAP_MB=1536
RUN NODE_OPTIONS="--max-old-space-size=${WEB_BUILD_HEAP_MB}" npm run build -- --webpack

FROM node:24-bookworm-slim AS runtime

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000

RUN groupadd --gid 10001 nextjs \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin nextjs

WORKDIR /app
COPY --from=builder --chown=10001:10001 /app/.next/standalone ./
COPY --from=builder --chown=10001:10001 /app/.next/static ./.next/static

USER 10001:10001
EXPOSE 3000

CMD ["node", "server.js"]

