# WattCoin Discord Bot

A feature-rich Discord bot for the WattCoin ecosystem providing wallet balance queries, network statistics, and alert notifications.

## Features

- 💰 **Balance Checking** - Query WATT token balances by wallet address
- 🌐 **Network Stats** - View active nodes, supply metrics, and network health
- 🔔 **Alerts** - Set up price and transaction notifications
- ⚡ **Dual Mode** - Supports both slash commands and prefix commands

## Quick Start

### Prerequisites

- Python 3.9+
- Discord Bot Token ([create one here](https://discord.com/developers/applications))

### Installation

1. Clone the repository:
```bash
git clone https://github.com/WattCoin-Org/wattcoin.git
cd wattcoin/discord-bot
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment:
```bash
cp .env.example .env
# Edit .env with your settings
```

4. Run the bot:
```bash
python bot.py
```

## Commands

### Slash Commands (Recommended)

- `/balance <wallet>` - Check WATT balance
- `/stats` - Show network statistics
- `/nodes` - List active nodes

## Configuration

See `.env.example` for all available options.

## License

MIT License
