FROM node:22-bookworm-slim@sha256:4b150b48b4116e2a22f2c39cc27025fbf4f153e2078fd3b14d159fdb5c7279da
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash git python3 ca-certificates curl iptables iproute2 ripgrep \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g @openai/codex@0.164.0 \
    && mkdir -p /root/.codex /workspace /opt/baseline \
    && git config --system user.name baseline-fixture \
    && git config --system user.email baseline-fixture@example.invalid \
    && mv /usr/local/bin/codex /usr/local/bin/codex-upstream
COPY codex-wrapper.py /usr/local/bin/codex
COPY connect-proxy.py /opt/baseline/connect-proxy.py
COPY api-broker.py /opt/baseline/api-broker.py
COPY lock-network.sh /opt/baseline/lock-network.sh
RUN chmod 755 /usr/local/bin/codex /opt/baseline/lock-network.sh \
    && codex --version
WORKDIR /workspace
