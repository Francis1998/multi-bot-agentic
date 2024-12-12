# multi-bot-agentic

![Coverage](https://img.shields.io/badge/coverage-85%25-brightgreen) ![CI](https://github.com/Francis1998/{repo}/actions/workflows/ci.yml/badge.svg) ![License](https://img.shields.io/badge/license-MIT-green)

> Multi-Agent Orchestration — powered by modern Python async architecture.

## Features

- **Bot engine** with configurable strategies
- **Orchestrator pipeline** with full observability
- **Async-first** design using `asyncio` + `aiohttp`
- **Type-safe** with full `mypy` compliance
- **Production-ready** with Docker, CI/CD, and structured logging

## Quick Start

```bash
git clone https://github.com/Francis1998/multi-bot-agentic.git
cd multi-bot-agentic
pip install -e ".[dev]"
cp .env.example .env
python -m multi_bot_agentic --help
```

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](ARCHITECTURE.md) | System design and component overview |
| [Configuration](docs/CONFIGURATION.md) | All configuration options |
| [Deployment](docs/DEPLOYMENT.md) | Production deployment guide |
| [Contributing](CONTRIBUTING.md) | Development and PR workflow |
| [Changelog](CHANGELOG.md) | Version history |

## License

MIT © [Francis1998](https://github.com/Francis1998)

*Last updated: 2024-12-12*
