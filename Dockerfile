# OpenRange image for Agent37 sandboxes (one sandbox per agent).
# Build + register with Agent37:   npx agent37 templates build . --name openrange
# The ROLE env var picks the agent: analyst | trader | both

FROM python:3.13-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY openrange ./openrange
RUN pip install --no-cache-dir -e .

COPY config ./config
COPY agents_harness ./agents_harness
COPY AGENTS.md ./
COPY .adal ./.adal

ENV ROLE=both
# Long-running process (Agent37 requires one): the live scheduler for this agent.
CMD ["sh", "-c", "python -m openrange.orchestrator.scheduler --role $ROLE"]
