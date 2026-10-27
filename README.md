# GoldBOT

An alert tool for Kalshi's daily gold markets ("Will gold be above $X at 5pm ET?").
It estimates the chance gold finishes above each strike, compares that with Kalshi's
prices, and flags contracts that look underpriced after fees.

**It never places orders.** It only reads public data and prints what it sees.

## How it decides

1. Reads gold's live price from Pyth, the price source Kalshi's daily gold markets settle on.
2. Measures how much gold has moved per day over the last 30 trading days (volatility).
3. For each strike, estimates the chance gold ends above it by settlement, skipping weekends.
4. Compares that chance with the YES and NO prices on Kalshi, minus the taker fee.
   If buying one side would be worth at least 5¢ per contract on average, it flags it.

Every scan is saved to `signals.csv`. After a few weeks we can check those signals
against how the markets actually settled. That tells us whether the model has any real edge
before any money is at risk.

## Setup (once)

You need Python 3.10 or newer.

```bash
git clone https://github.com/1400Donnie/GoldBOT.git
cd GoldBOT
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run it

```bash
python -m goldbot.scan --show-rules   # one scan, plus the market's official settlement rules
python -m goldbot.scan --watch 60     # scan every minute until you press Ctrl+C
```

Useful options:

| Option | What it does |
| --- | --- |
| `--min-edge 0.08` | Only flag trades worth at least 8¢ per contract |
| `--vol 0.012` | Use 1.2% daily volatility instead of downloading it |
| `--series KXGOLD15M` | Scan a different gold series |
| `--fee-rate 0.07` | Kalshi's taker fee multiplier (check Kalshi's fee schedule) |

Run the tests with `pytest`.

## Read this before trusting a signal

- The model is deliberately simple. It assumes gold moves randomly with constant volatility.
  Real gold jumps on news (Fed decisions, inflation data), so the model is overconfident on those days.
- Kalshi's prices already include everything traders know. A big "edge" usually means the model
  is missing something, not that the market is wrong.
- Check the market's rules (`--show-rules`) for the exact settlement source and time.
- Your API keys go in `.env`, which git ignores. Never commit or share your private key file.

## Next steps

1. Run the scanner for a few weeks and score `signals.csv` against real results.
2. Paper trading on Kalshi's demo site (fake money) using the API key in `.env`.
3. Only then, and only with your go-ahead, small real orders with hard limits.
