import nest_asyncio
nest_asyncio.apply()  # Enable nested event loops (helps in interactive environments)

import ccxt
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import mplfinance as mpf
import schedule
import time
from telegram import Bot, BotCommand, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CommandHandler, Application, CallbackQueryHandler
from pytz import utc
import asyncio
import threading

# Configure matplotlib to use a monospace font
plt.rcParams["font.family"] = "monospace"


class fib_ao_strategy:
    """
    A trading alert bot that uses the Awesome Oscillator and Fibonacci retracement levels
    on market OHLCV data to generate alerts and charts, and communicates via a Telegram bot.

    This bot:
      - Connects to a cryptocurrency exchange (via ccxt) to fetch historical market data.
      - Calculates technical indicators like the Awesome Oscillator.
      - Computes Fibonacci retracement levels based on recent swing changes.
      - Creates candlestick charts with retracement levels highlighted.
      - Sends alerts when the current market price nears these levels.
      - Provides an interactive Telegram bot interface for chart requests, help, and pausing alerts.
    """

    def __init__(self, info_file_path):
        """
        Initialize the fib_ao_strategy instance using configuration from a file.

        Reads configuration settings (in key=value format) from the file at info_file_path.
        Expected settings include:
          - symbol: Trading symbol (e.g., "BTC/USDT")
          - timeframe: Chart timeframe (e.g., "4h")
          - token_id: Telegram bot token.

        Sets up:
          - CCXT exchange connection for data retrieval.
          - The matplotlib figure holder.
          - Telegram Bot for alerts.
          - Alert tracking attributes.
          - The timestamp of the last candle to manage alert repetition.

        :param info_file_path: Path to the configuration text file.
        """
        with open(info_file_path, 'r') as info:
            information = info.readlines()
        settings = {}
        for line in information:
            if '=' in line:
                key, value = line.strip().split('=', 1)
                settings[key] = value
        self.symbol = settings["symbol"]
        self.timeframe = settings["timeframe"]
        self.ex = ccxt.gate()
        self.fig = None
        self.ret_limits = None
        self.fib_numbers = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1, 1.414, 1.618]
        self.bot = Bot(token=settings["token_id"])
        self.sent_alerts = set()  # Tracks which alerts have been sent for the current candle period.
        self.last_candle_start_time = None  # Timestamp for the start of the last candle.
        self.alerts_enabled = True  # Flag to control whether alerts are active.

    def __repr__(self):
        """
        Return the official string representation of the fib_ao_strategy instance.

        This representation includes the trading symbol and the timeframe.

        :return: A string representation of the instance.
        """
        return f"fib_ao_strategy(symbol='{self.symbol}', timeframe='{self.timeframe}')"

    def get_data(self):
        """
        Fetch and process the latest OHLCV market data.

        Workflow:
          - Retrieves raw OHLCV data from the exchange for the specified symbol and timeframe.
          - Converts the data into a pandas DataFrame with a datetime index.
          - Drops unnecessary columns and updates the class variable with the new data.
          - Checks if a new candle has started; if so, resets the alert tracking set.
          - Calculates technical indicators: Awesome Oscillator (ao) and Fibonacci levels.
          - Updates Fibonacci retracement limits and finally draws a candlestick chart with these levels.
        """
        exchange = self.ex
        raw = exchange.fetch_ohlcv(self.symbol, self.timeframe, limit=200)
        data = pd.DataFrame(raw, columns=["Time", "Open", "High", "Low", "Close", "Volume"])
        data.set_index(pd.to_datetime(data["Time"], unit="ms"), inplace=True)
        data.drop(["Time", "Volume"], axis=1, inplace=True)
        self.data = data

        # For 4h candles: if a new candle has started, reset sent alerts.
        latest_candle_time = data.index[-1]
        if self.last_candle_start_time is None or latest_candle_time != self.last_candle_start_time:
            self.last_candle_start_time = latest_candle_time
            self.sent_alerts.clear()

        # Calculate required indicators and charts
        self.ao()
        self.fibonacci(self.fib_numbers)
        self.define_limits()  # Ensure ret_limits is updated before strategy runs.
        self.draw_chart()

    def fetch_ticker(self):
        """
        Retrieve the current market ticker price for the configured symbol.

        :return: The last traded price as reported by the exchange.
        """
        exchange = self.ex
        self.cur_price = exchange.fetch_ticker(self.symbol)["last"]
        return self.cur_price

    def ao(self, sma_s=5, sma_l=34):
        """
        Calculate the Awesome Oscillator (AO) indicator from the market data.

        Process:
          - Computes the median price as the average of High and Low.
          - Calculates two simple moving averages (SMA): a short-term (sma_s) and a long-term (sma_l).
          - Determines the Awesome Oscillator as the difference between these two SMAs.
          - Derives the sign of the oscillator for further analysis (stored as 'ao_sign').
          - Updates the internal DataFrame with new columns ('awesome_osc' and 'ao_sign').

        :param sma_s: Window size for the short SMA (default is 5).
        :param sma_l: Window size for the long SMA (default is 34).
        """
        try:
            data = self.data.copy()
            median_price = (data["High"] + data["Low"]) / 2
            sma_short = median_price.rolling(window=sma_s).mean()
            sma_long = median_price.rolling(window=sma_l).mean()
            awesome_osc = sma_short - sma_long
            ao_sign = np.sign(awesome_osc)
            data["awesome_osc"] = awesome_osc
            data["ao_sign"] = ao_sign
            self.data = data.copy()
        except Exception:
            print("⚠️ Please run get_data() first!")

    def fibonacci(self, fib_levels: np.ndarray | list) -> list:
        """
        Calculate Fibonacci retracement levels based on recent oscillation swings.

        Process:
          - Marks changes in the 'ao_sign' column to detect swing points.
          - Selects the three most recent swing points.
          - Determines whether the move (swing) was ascending or descending based on the median of the second segment.
          - Computes Fibonacci levels by interpolating between the calculated high and low based on the provided ratios.
          - The resulting levels are stored as both a list and a pandas Series.

        :param fib_levels: List or array of Fibonacci ratio values (e.g., [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1]).
        :return: A list of calculated Fibonacci retracement price levels.
        :raises ValueError: If the trend direction cannot be determined.
        """
        data = self.data.copy()
        # Identify swing points where the sign of 'ao_sign' changes.
        data['chunks'] = (data['ao_sign'] != data['ao_sign'].shift(1)).astype(int).shift(-1)
        filtered_data_time = data[data["chunks"] != 0].dropna().iloc[-3:].index
        first_chunk, second_chunk, third_chunk = filtered_data_time[0], filtered_data_time[1], filtered_data_time[2]
        if data.loc[second_chunk:third_chunk, "ao_sign"].median() == 1:
            # Descending scenario.
            low = data.loc[first_chunk:second_chunk, "Low"].min()
            high = data.loc[second_chunk:third_chunk, "High"].max()
            side = "desc"
        elif data.loc[second_chunk:third_chunk, "ao_sign"].median() == -1:
            # Ascending scenario.
            high = data.loc[first_chunk:second_chunk, "High"].max()
            low = data.loc[first_chunk:second_chunk, "Low"].min()
            side = "asc"
        else:
            raise ValueError("Something went wrong calculating Fibonacci levels!")
        ret = []
        # Calculate retracement levels based on trend direction.
        if side == "asc":
            for i in fib_levels:
                ret.append(high - (high - low) * i)
        elif side == "desc":
            for i in fib_levels:
                ret.append(high - (high - low) * (1 - i))
        else:
            raise ValueError("'side' should be either 'asc' or 'desc'")
        fib_ret = pd.Series(data=ret, index=fib_levels)
        self.ret_list = ret
        self.ret_series = fib_ret


    def draw_chart(self):
        """
        Draws real-time chart with Fibonacci retracement horizontal lines.
        """
        # Use mplfinance to draw the candlestick chart with horizontal lines.
        data = self.data.copy()
        fib_rets = self.ret_list
        self.fig, axes = mpf.plot(
                            data[["Open", "High", "Low", "Close"]],
                            type='candle',
                            style='charles',
                            figsize=(15, 8),
                            title=f"{self.symbol} {self.timeframe} with Fibonacci ret. levels",
                            hlines=fib_rets,
                            returnfig=True
                            )
        plt.close(self.fig)

    def define_limits(self):
        """
        Define upper and lower price limits around Fibonacci retracement levels for alert triggering.

        For each Fibonacci level, computes:
          - A lower limit (0.4% below the level).
          - An upper limit (0.4% above the level).
        These bands are stored in a pandas DataFrame (self.ret_limits) and later used by the strategy
        to determine when to send an alert.
        """
        data = self.data.copy()
        ret_series = self.ret_series
        ret_limits = pd.DataFrame()
        ret_limits["fib_rets"] = ret_series
        ret_limits["limit_down"] = ret_series - (ret_series * 0.004)
        ret_limits["limit_up"] = ret_series + (ret_series * 0.004)
        self.ret_limits = ret_limits.copy()

    def strategy(self, update=None):
        """
        Execute the alert strategy based on current market price in relation to Fibonacci levels.

        Process:
          - Only proceeds if alerts are enabled.
          - Fetches the current ticker price.
          - Checks if the price is within the acceptable band (limit_up and limit_down)
            around any Fibonacci level.
          - For each matched Fibonacci level (that has not already triggered an alert for the current candle),
            outputs an alert message and marks that level as alerted.
          - If data is not ready, notifies the user to run /getdata.

        :param update: Optional parameter from Telegram update context (not used in background alerts).
        """
        # Only execute strategy if alerts are enabled.
        if not self.alerts_enabled:
            return
    
        cur_price = self.fetch_ticker()
        try:
            if self.ret_limits is not None and not self.ret_limits.empty:
                ret_limits = self.ret_limits.copy()
                limit_check = ret_limits[
                    (ret_limits["limit_up"] > cur_price) &
                    (ret_limits["limit_down"] < cur_price)
                ].index
                if not limit_check.empty:
                    for idx in limit_check:
                        if idx not in self.sent_alerts:
                            message = f"💡 Alert! Current price: {cur_price} for Fibonacci level {idx} 🔔"
                            print(message)
                            self.sent_alerts.add(idx)
                            # If chat_id and bot_loop are available, send the Telegram message.
                            if hasattr(self, 'chat_id') and hasattr(self, 'bot_loop'):
                                asyncio.run_coroutine_threadsafe(
                                    self.bot.send_message(chat_id=self.chat_id, text=message, parse_mode='Markdown'),
                                    self.bot_loop
                                )
                            else:
                                print("No chat_id or bot_loop available. Ensure /start is executed in Telegram.")
            else:
                print("💬 Please wait until data is ready! (Hint: Run /getdata if needed.)")
        except Exception as e:
            print(f"❌ Failed: {e}")



    def start_bot(self):
        """
        Start the Telegram bot to manage interactive commands and inline keyboard callbacks.

        This method sets up asynchronous command handlers for:
          - /start: Display a welcome message and resume alerts.
          - /help: Show detailed help information.
          - /chart: Generate and send the current market chart.
          - /stop: Pause alerts.

        Additionally:
          - Handles inline keyboard button presses via a callback.
          - Registers commands with Telegram for an improved interactive experience.
          - Runs the polling loop in an asyncio event loop.
        """
        async def run_async():
            application = Application.builder().token(self.bot.token).build()
    
            # Save the running event loop for later use
            self.bot_loop = asyncio.get_running_loop()
    
            # /start: Welcome message with menu inline keyboard.
            async def start(update, context):
                # Save the user's chat id for later alert messages.
                self.chat_id = update.effective_message.chat_id
                if not self.alerts_enabled:
                    self.alerts_enabled = True
                    await update.effective_message.reply_text("🚀 Alerts resumed!", parse_mode="Markdown")
                else:
                    welcome_message = (
                        "👋 Hello there! I'm your friendly market alert bot.\n\n"
                        "What I can do:\n"
                        "• Provide market data & alerts based on the Awesome Oscillator & Fibonacci levels 📈\n"
                        "• Generate detailed candlestick charts enriched with Fibonacci retracement levels 🖼️\n"
                        "• Display a current market snapshot including ticker, symbol, timeframe and time ⏰\n\n"
                        "Select a command below:"
                    )
                    keyboard = [
                        [InlineKeyboardButton("Chart 📈", callback_data="chart"),
                         InlineKeyboardButton("Help 🧐", callback_data="help")],
                        [InlineKeyboardButton("Stop 🚫", callback_data="stop")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await update.effective_message.reply_text(welcome_message, parse_mode="Markdown", reply_markup=reply_markup)
    
            # /help: Display help information.
            async def help_handler(update, context):
                help_text = (
                    "🤖 *Market Alert Bot Help:*\n\n"
                    "/start - Start/resume alerts and view available features 😊\n"
                    "/help - Show this help message and list features 🧐\n"
                    "/chart - Get the current market chart image 🖼️\n"
                    "/stop - Pause alerts 🚫\n\n"
                    "I'm here to fetch market data, compute technical indicators, and alert you when "
                    "conditions are met. Choose a button from the menu or type a command!"
                )
                keyboard = [
                    [InlineKeyboardButton("Chart 📈", callback_data="chart"),
                     InlineKeyboardButton("Stop 🚫", callback_data="stop")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.effective_message.reply_text(help_text, parse_mode="Markdown", reply_markup=reply_markup)

            # /chart: Generate and send the current chart.
            async def chart(update, context):
                from io import BytesIO
                data = self.data.copy()
                fib_rets = self.ret_list
                buf = BytesIO()
                # Generate the chart figure with Fibonacci levels using mplfinance.
                fig, _ = mpf.plot(
                    data[["Open", "High", "Low", "Close"]],
                    type='candle',
                    style='charles',
                    figsize=(15, 8),
                    title=f"{self.symbol} {self.timeframe} with Fibonacci ret. levels",
                    hlines=fib_rets,
                    returnfig=True
                )
                fig.savefig(buf, format='png')
                buf.seek(0)
                plt.close(fig)
    
                current_price = self.fetch_ticker()
                current_time = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
                chart_caption = (
                    "😎 *Here's your current chart!*\n\n"
                    f"⏰ Current Time: {current_time}\n"
                    f"💲 Ticker: {current_price}\n"
                    f"🔖 Symbol: {self.symbol}\n"
                    f"📊 Timeframe: {self.timeframe}"
                )
                await update.effective_message.reply_photo(buf, caption=chart_caption, parse_mode="Markdown")

            # /stop: Pause alerts.
            async def stop_handler(update, context):
                self.alerts_enabled = False
                await update.effective_message.reply_text("👋 Alerts paused. Send /start to resume!", parse_mode="Markdown")
    
            # Handle inline keyboard button presses.
            async def button_handler(update, context):
                query = update.callback_query
                await query.answer()  # Acknowledge the callback.
                data = query.data
                if data == "chart":
                    await chart(update, context)
                elif data == "help":
                    await help_handler(update, context)
                elif data == "stop":
                    await stop_handler(update, context)

            # Add handlers to the application.
            application.add_handler(CommandHandler("start", start))
            application.add_handler(CommandHandler("help", help_handler))
            application.add_handler(CommandHandler("chart", chart))
            application.add_handler(CommandHandler("stop", stop_handler))
            application.add_handler(CallbackQueryHandler(button_handler))
    
            # Register commands for Telegram.
            commands = [
                BotCommand("start", "Start/resume alerts 😊"),
                BotCommand("help", "Help and info 🧐"),
                BotCommand("chart", "Get current chart image 🖼️"),
                BotCommand("stop", "Pause alerts 🚫"),
            ]
            await application.bot.set_my_commands(commands)
            await application.run_polling()
    
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        new_loop.run_until_complete(run_async())


    def scheduler_loop(self):
        """
        Continuously check and run any scheduled tasks.

        Uses the schedule library to run tasks that have been scheduled (such as data fetching
        and strategy evaluation). Sleeps briefly between checks to avoid excessive CPU usage.
        """
        while True:
            schedule.run_pending()
            time.sleep(2)

    def run(self):
        """
        Start the overall bot functionality including data fetching, strategy execution,
        and the Telegram bot interface.

        Workflow:
          - Perform an initial data fetch and compute indicators.
          - Clear any existing schedules and set up new recurring tasks:
              • Update market data every 4 seconds.
              • Run the alert strategy every 10 seconds.
          - Launch both the Telegram bot and the scheduler in separate daemon threads.
          - Wait for both threads to run indefinitely.
        """
        # Initial data fetch and indicator calculations.
        self.get_data()
        schedule.clear()
        schedule.every(4).hours.do(self.get_data)
        schedule.every(20).seconds.do(lambda: self.strategy())

        # Use threading to run the bot and the scheduler concurrently.
        bot_thread = threading.Thread(target=self.start_bot, daemon=True)
        scheduler_thread = threading.Thread(target=self.scheduler_loop, daemon=True)
        bot_thread.start()
        scheduler_thread.start()

        bot_thread.join()
        scheduler_thread.join()


# Instantiate and run the bot.
f = fib_ao_strategy("information.txt")
f.run()
