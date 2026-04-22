FROM node:23.3.0-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    g++ \
    git \
    make \
    python3 \
    unzip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN npm install -g bun

ENV PATH="/root/.bun/bin:/home/node/.bun/bin:$PATH"

RUN echo '#!/bin/bash\nexec /app/node_modules/.bin/elizaos "$@"' > /usr/local/bin/elizaos && \
    chmod +x /usr/local/bin/elizaos

WORKDIR /app

COPY package.json bun.lock* ./
RUN bun install

COPY . .
RUN bun run build

COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

RUN chown -R node:node /app
RUN mkdir -p /home/node/.bun && chown -R node:node /home/node/.bun

USER node

EXPOSE 3000
# entrypoint: map Railway $PORT -> $SERVER_PORT for @elizaos/server
CMD ["/app/docker-entrypoint.sh"]
