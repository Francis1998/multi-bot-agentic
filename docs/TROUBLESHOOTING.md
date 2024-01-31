# Troubleshooting Orchestrator

*multi-bot-agentic — 2024-01-31*

## Overview

This guide covers troubleshooting orchestrator for the `multi-bot-agentic` project.

## Prerequisites

- Python 3.10+
- Redis (if using distributed mode)
- Environment variables configured (see `.env.example`)

## Quick Start

```bash
# Install dependencies
pip install -e ".[dev]"

# Copy and configure environment
cp .env.example .env

# Run the multi_bot_agentic module
python -m multi_bot_agentic --help
```

## Common Scenarios

### Scenario 1: Basic Orchestrator Usage

```python
from multi_bot_agentic import Orchestrator

client = Orchestrator(config)
result = client.run()
print(result)
```

### Scenario 2: Advanced Configuration

```python
from multi_bot_agentic.config import Settings

settings = Settings(
    max_retries=3,
    timeout=30,
    log_level="INFO",
)
```

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| `ConnectionError` | API endpoint unreachable | Check `BASE_URL` in `.env` |
| `TimeoutError` | Request took too long | Increase `timeout` setting |
| `AuthError` | Invalid or expired token | Rotate API key |

## See Also

- [README](../README.md)
- [ARCHITECTURE](../ARCHITECTURE.md)
- [API Reference](./API.md)
