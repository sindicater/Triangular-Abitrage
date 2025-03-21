# <span style="color:blue">Triangular-Abitrage</span>
will find code in Master  Branch


# <span style="color:blue">KuCoin Triangular Arbitrage Bot</span>

## <span style="color:green">Overview</span>
This Python script is a **triangular arbitrage trading bot** designed for the KuCoin cryptocurrency exchange. It identifies and executes profitable arbitrage opportunities by analyzing trading pairs, calculating potential profits, and automatically placing market orders using the KuCoin API.

---

## <span style="color:purple">Features</span>
- **Market Data Retrieval**: Fetches real-time ticker data and symbol precisions.
- **Account Management**: Checks available balances to ensure sufficient funds.
- **Affordable Pair Analysis**: Finds trading pairs within your USDT investment budget.
- **Multi-Pair Detection**: Identifies coins with multiple pairs (e.g., major coins + USDT).
- **Liquidity Check**: Filters based on a minimum 24h volume (default: *$100,000 USD*).
- **Arbitrage Calculation**: Computes profits with a default trading fee of **0.1%**.
- **Trade Execution**: Executes the best profitable trade automatically.
- **User Interface**: Displays colorful tables and updates using `colorama` and `tabulate`.

---

## <span style="color:orange">Requirements</span>
- **Python 3.6+**
- **Dependencies**:
  - `kucoin-python` (`pip install kucoin-python`)
  - `colorama` (`pip install colorama`) - *For colored terminal output*
  - `tabulate` (`pip install tabulate`) - *For pretty tables*

---

## <span style="color:blue">Setup</span>
1. **Install Dependencies**:
   ```bash
   pip install kucoin-python colorama tabulate
   ```
2. **Configure API Credentials**:
   - Update the script with your KuCoin API details:
     ```python
     API_KEY = "your_api_key"
     API_SECRET = "your_api_secret"
     API_PASSPHRASE = "your_api_passphrase"
     ```
   - Get these from KuCoin’s API Management page.

3. **Run the Script**:
   ```bash
   python arbitrage_bot.py
   ```

---

## <span style="color:green">Usage</span>
1. **Start the Bot**: Run the script in a terminal.
2. **Input Investment Amount**: Enter your USDT investment (min: **0.1 USDT**).
3. **Review Output**: See affordable pairs, arbitrage paths, and trade results.
4. **Monitor Results**: Check execution summaries with profits and timing.

---

## <span style="color:purple">Key Functions</span>
- **`get_symbol_precisions()`**: Gets precision details for trading pairs.
- **`get_all_tickers()`**: Fetches prices and volumes.
- **`get_account_balances()`**: Retrieves available funds.
- **`find_affordable_pairs()`**: Identifies affordable trading pairs.
- **`find_best_triangular_arbitrage()`**: Calculates arbitrage opportunities.
- **`execute_triangular_trade()`**: Executes trades step-by-step.
- **`main()`**: Runs the bot’s core logic.

---

## <span style="color:orange">Configuration</span>
- **Constants**:
  - `MAJOR_COINS`: `{BTC, ETH, KCS, BNB, XRP, USDC}`
  - `TRADING_FEE`: **0.001** (0.1%)
  - `MIN_ORDER_SIZE`: **0.1 USDT**
  - `LIQUIDITY_THRESHOLD`: **$100,000 USD**

- Edit these in the script to tweak behavior.

---

## <span style="color:red">Safety Notes</span>
- **API Security**: *Never share credentials in the script.*
- **Funds Risk**: Test with small amounts first.
- **Rate Limits**: Avoid excessive API calls.
- **Error Handling**: Basic checks included, but monitor for issues.

---

## <span style="color:blue">Limitations</span>
- **Market Volatility**: Prices may shift during execution.
- **API Dependency**: Requires KuCoin API uptime.
- **Single Exchange**: KuCoin-only; no cross-exchange support.

---

## <span style="color:green">Example Output</span>
```
How much do you want to invest (in USDT)? 100

Fetching affordable trading pairs for 100.000000 USDT...

Coins with Multiple Trading Pairs:
+------+--------------------+---------------------------+-----------------+------------+
| Coin | Pairs              | Affordable Units (USDT)   | 24h Volume (USD)| Liquidity  |
+------+--------------------+---------------------------+-----------------+------------+
| XRP  | XRP-BTC, XRP-USDT  | XRP-USDT: 200.000000      | 150000.00       | Liquid     |
+------+--------------------+---------------------------+-----------------+------------+

Triangular Arbitrage Paths:
+------+---------------+--------------------------+-------------------+
| Coin | Profit (USDT) | Path                     | Affordable Units  |
+------+---------------+--------------------------+-------------------+
| XRP  | 0.500000      | XRP-USDT -> XRP-BTC -> BTC-USDT | 200.000000  |
+------+---------------+--------------------------+-------------------+

Trade Results:
  Path Followed: XRP-USDT -> XRP-BTC -> BTC-USDT
  Time Taken: 2.3456 seconds
  Actual Profit: 0.450000 USDT
  Actual Profit Percentage: 0.45%
```



### Code Rating (Unchanged): 8/10
The rating remains as previously assessed—see the prior response for details. The colorful README enhances presentation but doesn’t affect the code’s functionality or quality.
