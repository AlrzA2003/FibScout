# FibScout

FibScout is a Python project that leverages technical indicators—specifically the Awesome Oscillator and Fibonacci retracement levels—for market trend analysis and real-time alerts in the cryptocurrency space. FibScout fetches live data using the [ccxt](https://github.com/ccxt/ccxt) library (specifically `ccxt.binance()`), generates detailed candlestick charts with Fibonacci overlays via mplfinance, and sends alerts directly to your Telegram app through a custom bot.

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Setup](#setup)
- [Usage](#usage)
- [How It Works](#how-it-works)
- [Risk Disclaimer](#risk-disclaimer)
- [Resources](#resources)
- [Contributing](#contributing)
- [License](#license)

## Features

- **Real-Time Data Fetching:** Retrieves live OHLCV data from crypto exchanges using ccxt.
- **Technical Analysis:** Calculates the Awesome Oscillator and dynamically computes Fibonacci retracement levels.
- **Interactive Charting:** Generates candlestick charts with Fibonacci horizontal lines and legends using mplfinance and Matplotlib.
- **Telegram Alert Bot:** Sends real-time alerts to your Telegram chat when market conditions are met.
- **Asynchronous and Scheduled Tasks:** Uses multithreading and asyncio to concurrently manage data updates, strategy evaluations, and bot interactions.

## Prerequisites

- Python 3.7+
- A cryptocurrency exchange account (e.g., Binance via `ccxt` or similar)
- A Telegram account and a bot token (from [BotFather](https://core.telegram.org/bots#3-how-do-i-create-a-bot))
- Basic understanding of Python and algorithmic trading principles

## Installation

1. Clone this repository:

    ```bash
    git clone https://github.com/AlrzA2003/FibScout.git
    cd FibScout
    ```

2. Install the required packages:

    ```bash
    pip install -r requirements.txt
    ```

    *Optional: To ensure compatibility, you may also install from a specific requirements file if provided.*

## Setup

1. **Configuration File:**  
   Create a file named `information.txt` in the root directory with the following key-value pairs:

    ```
    symbol=BTC/USDT
    timeframe=4h
    token_id=YOUR_TELEGRAM_BOT_TOKEN
    ```

   Adjust the parameters as needed.

2. **Environment:**  
   Ensure that any additional API keys or settings needed for the cryptocurrency exchange (via `ccxt.binance()`) are properly configured.

## Usage

After setting up, run the project with:

```bash
python FibScout.py
```

The script will:

- Connect to the cryptocurrency exchange and fetch market data.
- Compute technical indicators and generate candlestick charts with Fibonacci retracement levels.
- Start a Telegram bot to interact with you and send real-time alert messages when market conditions are triggered.

## How It Works

FibScout operates as follows:

1. **Data Acquisition:** Fetches live OHLCV data from a crypto exchange using `ccxt.binance()`.
2. **Technical Analysis:** Computes the Awesome Oscillator and determines key Fibonacci retracement levels by analyzing recent market trends.
3. **Charting:** Plots these levels on candlestick charts with mplfinance and Matplotlib, complete with color-coded horizontal lines and legends.
4. **Real-Time Alerts:** Sends Telegram messages with alert information when the current price moves within specific Fibonacci bands.
5. **Asynchronous Execution:** Runs the Telegram bot (handling commands such as `/start`, `/help`, `/chart`, `/stop`) on the main thread, while a scheduler in a background thread continuously triggers data updates and strategy evaluations.

## Risk Disclaimer

Trading cryptocurrencies involves significant risk and is not suitable for everyone. FibScout is designed for educational and experimental purposes only. Please consider the following:

- Trading strategies based on technical indicators carry inherent risks.
- Never trade with funds you cannot afford to lose.
- The author is not responsible for any financial losses incurred using this software.
- Always test with a demo environment or paper trading before trading real funds.

## Resources

The development of FibScout was guided by the following resources:

1. **[ccxt Library](https://github.com/ccxt/ccxt)** – GitHub
2. **[mplfinance](https://github.com/matplotlib/mplfinance)** – Documentation
3. **[python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)** – Documentation
4. **Data Analysis with Pandas and NumPy** – Various online courses and tutorials

## Contributing

Contributions to FibScout are welcome! Please feel free to open issues or submit pull requests with suggestions for improvements, new features, or bug fixes.

## License

This project is licensed under the MIT License – see the [LICENSE](LICENSE) file for details.
