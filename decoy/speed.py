import time
from kucoin.client import Market, User, Trade
from colorama import init, Fore, Style
from tabulate import tabulate
import threading
from cachetools import TTLCache
import pandas as pd

init()

API_KEY = "67aa06d2ee26850001561d50"
API_SECRET = "86e68f93-54a3-4f03-814b-7528d40382ec"
API_PASSPHRASE = "2003Thiongo"

market_client = Market(url='https://api.kucoin.com')
user_client = User(key=API_KEY, secret=API_SECRET, passphrase=API_PASSPHRASE, url='https://api.kucoin.com')
trade_client = Trade(key=API_KEY, secret=API_SECRET, passphrase=API_PASSPHRASE, url='https://api.kucoin.com')
MAJOR_COINS = {'BTC', 'ETH', 'KCS', 'BNB', 'XRP', 'USDC'}
TRADING_FEE = 0.001
MIN_ORDER_SIZE = 0.1
LIQUIDITY_THRESHOLD = 130000

# Caches with TTL (10s for tickers, 1hr for precisions)
ticker_cache = TTLCache(maxsize=1, ttl=10)
precision_cache = TTLCache(maxsize=1, ttl=3600)

def get_symbol_precisions():
    try:
        symbols = market_client.get_symbol_list()
        if not isinstance(symbols, list):
            print(f"Error: Unexpected response format from get_symbol_list(): {symbols}")
            return {}
        precision_dict = {}
        for symbol in symbols:
            if all(k in symbol for k in ['symbol', 'quantityPrecision', 'pricePrecision', 'baseMinSize']):
                precision_dict[symbol['symbol']] = {
                    'quantityPrecision': symbol['quantityPrecision'],
                    'pricePrecision': symbol['pricePrecision'],
                    'baseMinSize': float(symbol['baseMinSize'])
                }
        return precision_dict
    except Exception as e:
        print(f"Error fetching symbol precisions: {e}")
        return {}

def get_all_tickers():
    try:
        tickers = market_client.get_all_tickers()['ticker']
        return tickers
    except Exception as e:
        print(f"Error fetching tickers: {e}")
        return []

def get_account_balances():
    try:
        accounts = user_client.get_account_list()
        balances = {acc['currency']: float(acc['available']) for acc in accounts if float(acc['available']) > 0}
        return balances
    except Exception as e:
        print(f"Error fetching balances: {e}")
        return {}

def fetch_initial_data():
    results = {}
    threads = [
        threading.Thread(target=lambda: results.update({'tickers': get_all_tickers()})),
        threading.Thread(target=lambda: results.update({'precisions': get_symbol_precisions()})),
        threading.Thread(target=lambda: results.update({'balances': get_account_balances()}))
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results.get('tickers', []), results.get('precisions', {}), results.get('balances', {})

def get_all_tickers_cached():
    if 'tickers' not in ticker_cache:
        tickers = get_all_tickers()
        ticker_cache['tickers'] = tickers
    return ticker_cache['tickers']

def get_symbol_precisions_cached():
    if 'precisions' not in precision_cache:
        precisions = get_symbol_precisions()
        precision_cache['precisions'] = precisions
    return precision_cache['precisions']

def find_affordable_pairs_vectorized(investment_amount, tickers):
    df = pd.DataFrame(tickers)
    df['last'] = pd.to_numeric(df['last'], errors='coerce')
    df = df.dropna(subset=['last'])
    affordable = df[df['last'] <= investment_amount].copy()
    affordable[['base_currency', 'quote_currency']] = affordable['symbol'].str.split('-', expand=True)
    return affordable.to_dict('records')

def find_coins_with_multiple_pairs(affordable_pairs):
    base_currency_count = {}
    base_currency_pairs = {}
    for pair in affordable_pairs:
        base = pair['base_currency']
        if base in base_currency_count:
            base_currency_count[base] += 1
            base_currency_pairs[base].append(pair)
        else:
            base_currency_count[base] = 1
            base_currency_pairs[base] = [pair]
    multi_pair_coins = {}
    for base, count in base_currency_count.items():
        if count > 1:
            pairs = base_currency_pairs[base]
            has_major_pair = any(pair['quote_currency'] in MAJOR_COINS for pair in pairs)
            has_usdt_pair = any(pair['quote_currency'] == 'USDT' for pair in pairs)
            if has_major_pair and has_usdt_pair:
                multi_pair_coins[base] = pairs
    return multi_pair_coins

def calculate_affordable_units(investment_amount, multi_pair_coins):
    affordable_units = {}
    for coin, pairs in multi_pair_coins.items():
        units_per_pair = {}
        for pair in pairs:
            if pair['quote_currency'] == 'USDT':
                price = pair['price']
                units = investment_amount / price
                units_per_pair[pair['symbol']] = units
        if units_per_pair:
            affordable_units[coin] = units_per_pair
    return affordable_units

def print_coins_with_multiple_pairs(multi_pair_coins, affordable_units, ticker_dict):
    table = []
    headers = ["Coin", "Pairs", "Affordable Units (USDT)", "24h Volume (USD)", "Liquidity"]
    for coin, pairs in multi_pair_coins.items():
        pairs_str = ", ".join([pair['symbol'] for pair in pairs])
        units_info = affordable_units.get(coin, {})
        units_str = ", ".join([f"{symbol}: {units:.6f}" for symbol, units in units_info.items()])
        volume_usd = sum(ticker_dict.get(pair['symbol'], {}).get('volValue', 0) for pair in pairs)
        liquidity_status = f"{Fore.GREEN}Liquid{Style.RESET_ALL}" if volume_usd >= LIQUIDITY_THRESHOLD else f"{Fore.RED}Illiquid{Style.RESET_ALL}"
        table.append([coin, pairs_str, units_str, f"{volume_usd:.2f}", liquidity_status])
    print(f"\n{Fore.BLUE}Coins with Multiple Trading Pairs:{Style.RESET_ALL}")
    print(tabulate(table, headers=headers, tablefmt="pretty"))
    return table

def pre_filter_liquid_pairs(multi_pair_coins, ticker_dict):
    liquid_coins = {}
    for coin, pairs in multi_pair_coins.items():
        volume_usd = sum(ticker_dict.get(pair['symbol'], {}).get('volValue', 0) for pair in pairs)
        if volume_usd >= LIQUIDITY_THRESHOLD:
            liquid_coins[coin] = pairs
    return liquid_coins

def find_best_triangular_arbitrage(multi_pair_coins, investment_amount, ticker_dict, fee_rate=TRADING_FEE):
    arbitrage_opportunities = []
    for coin, pairs in multi_pair_coins.items():
        usdt_pair = None
        major_coin_pairs = []
        for pair in pairs:
            if pair['quote_currency'] == 'USDT':
                usdt_pair = pair
            elif pair['quote_currency'] in MAJOR_COINS:
                major_coin_pairs.append(pair)
        if not usdt_pair or not major_coin_pairs:
            continue
        for major_coin_pair in major_coin_pairs:
            usdt_price = usdt_pair['price'] * 1.005
            units_x = investment_amount / usdt_price
            amount_x = units_x * (1 - fee_rate)
            major_coin = major_coin_pair['quote_currency']
            x_to_major_price = major_coin_pair['price'] / 1.005
            units_major = amount_x * x_to_major_price
            amount_major = units_major * (1 - fee_rate)
            major_to_usdt_symbol = f"{major_coin}-USDT"
            major_to_usdt_price = ticker_dict.get(major_to_usdt_symbol, {}).get('last', 0) / 1.005
            if major_to_usdt_price == 0:
                continue
            final_usdt = amount_major * major_to_usdt_price * (1 - fee_rate)
            profit = final_usdt - investment_amount
            path = f"{usdt_pair['symbol']} -> {major_coin_pair['symbol']} -> {major_to_usdt_symbol}"
            arbitrage_opportunities.append({
                'coin': coin,
                'profit': profit,
                'path': path,
                'units': units_x
            })
    arbitrage_opportunities.sort(key=lambda x: x['profit'], reverse=True)
    return arbitrage_opportunities if arbitrage_opportunities else []

def print_arbitrage_paths(arbitrage_opportunities):
    table = []
    headers = ["Coin", "Profit (USDT)", "Path", "Affordable Units"]
    for opp in arbitrage_opportunities:
        profit_color = Fore.GREEN if opp['profit'] > 0 else Fore.RED
        profit_str = f"{profit_color}{opp['profit']:.6f}{Style.RESET_ALL}"
        table.append([opp['coin'], profit_str, opp['path'], f"{opp['units']:.6f}"])
    print(f"\n{Fore.CYAN}Triangular Arbitrage Paths:{Style.RESET_ALL}")
    print(tabulate(table, headers=headers, tablefmt="pretty"))

def execute_triangular_trade(path, units, ticker_dict, initial_usdt, precisions):
    try:
        start_time = time.time()
        steps = path.split(' -> ')
        print(f"\nExecuting trade: {path} with {units:.6f} units")
        pair1 = steps[0]
        base1, quote1 = pair1.split('-')
        price1 = ticker_dict.get(pair1, {}).get('last', float('inf'))
        if price1 == float('inf'):
            print(f"Error: No price found for {pair1}")
            return False, 0, 0, 0
        precision1 = precisions.get(pair1, {'quantityPrecision': 2, 'pricePrecision': 2, 'baseMinSize': 0.1})
        amount_usdt = units * price1
        if amount_usdt < MIN_ORDER_SIZE:
            print(f"Error: Initial funds {amount_usdt:.6f} USDT below minimum {MIN_ORDER_SIZE} USDT")
            return False, 0, 0, 0
        amount_usdt_rounded = max(round(amount_usdt, precision1['pricePrecision']), MIN_ORDER_SIZE)
        units_adjusted = amount_usdt_rounded / price1
        if units_adjusted < precision1['baseMinSize']:
            print(f"Error: Units {units_adjusted:.6f} {base1} below minimum {precision1['baseMinSize']} for {pair1}")
            return False, 0, 0, 0
        units_str1 = f"{units_adjusted:.{precision1['quantityPrecision']}f}"
        amount_usdt_str = f"{amount_usdt_rounded:.{precision1['pricePrecision']}f}"
        pair2 = steps[1]
        base2, quote2 = pair2.split('-')
        precision2 = precisions.get(pair2, {'quantityPrecision': 2, 'pricePrecision': 2, 'baseMinSize': 0.1})
        units_str2 = f"{units_adjusted:.{precision2['quantityPrecision']}f}"
        if units_adjusted < precision2['baseMinSize']:
            print(f"Error: Units {units_adjusted:.6f} {base2} below minimum {precision2['baseMinSize']} for {pair2}")
            return False, 0, 0, 0
        pair3 = steps[2]
        price3 = ticker_dict.get(pair3, {}).get('last', float('inf'))
        if price3 == float('inf'):
            print(f"Error: No price found for {pair3}")
            return False, 0, 0, 0
        precision3 = precisions.get(pair3, {'quantityPrecision': 8, 'pricePrecision': 2, 'baseMinSize': 0.00001})
        acquired_units = (units_adjusted * ticker_dict[pair2]['last']) * (1 - TRADING_FEE)
        if acquired_units < precision3['baseMinSize']:
            print(f"Error: {quote2} amount {acquired_units:.8f} below minimum {precision3['baseMinSize']} for {pair3}")
            return False, 0, 0, 0
        if acquired_units * price3 < MIN_ORDER_SIZE:
            print(f"Error: {quote2} value {acquired_units:.8f} * {price3} = {acquired_units * price3:.6f} USDT below minimum {MIN_ORDER_SIZE} USDT")
            return False, 0, 0, 0
        acquired_units_str = f"{acquired_units:.{precision3['quantityPrecision']}f}"
        results = [None] * 3
        def place_order(index, symbol, side, size=None, funds=None):
            try:
                order = trade_client.create_market_order(symbol, side, size=size, funds=funds)
                results[index] = order['orderId']
            except Exception as e:
                results[index] = f"Error: {e}"
        threads = [
            threading.Thread(target=place_order, args=(0, pair1, 'buy', None, amount_usdt_str)),
            threading.Thread(target=place_order, args=(1, pair2, 'sell', units_str2)),
            threading.Thread(target=place_order, args=(2, pair3, 'sell', acquired_units_str))
        ]
        print(f"Debug: Using {amount_usdt_str} USDT to buy {units_str1} {base1} (price: {price1})")
        print(f"Debug: Selling {units_str2} {base2} for {quote2}")
        print(f"Debug: Selling {acquired_units_str} {quote2} back to USDT")
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        for i, result in enumerate(results):
            if isinstance(result, str) and "Error" in result:
                print(f"Step {i+1} failed: {result}")
                return False, 0, 0, 0
            print(f"Step {i+1}: Order ID: {result}")
        end_time = time.time()
        execution_time = end_time - start_time
        final_balances = get_account_balances()
        final_usdt = final_balances.get('USDT', 0)
        profit = final_usdt - (initial_usdt - amount_usdt_rounded)
        return True, execution_time, profit, amount_usdt_rounded
    except Exception as e:
        print(f"Error executing trade: {e}")
        return False, 0, 0, 0

def main():
    while True:
        while True:
            try:
                investment_amount = float(input("How much do you want to invest (in USDT)? "))
                if investment_amount <= 0:
                    print("Please enter a positive amount.")
                    continue
                if investment_amount < MIN_ORDER_SIZE:
                    print(f"Investment must be at least {MIN_ORDER_SIZE} USDT.")
                    continue
                break
            except ValueError:
                print("Invalid input. Please enter a numeric value.")
        start_time = time.time()
        print(f"\nFetching affordable trading pairs for {investment_amount:.6f} USDT...\n")
        all_tickers, precisions, balances = fetch_initial_data()
        ticker_dict = {t['symbol']: {'last': float(t['last']), 'volValue': float(t['volValue'])}
                      for t in all_tickers if t['last'] is not None}
        if not ticker_dict:
            print("No valid ticker data available. Continuing to next iteration.")
            continue
        affordable_pairs = find_affordable_pairs_vectorized(investment_amount, all_tickers)
        if not affordable_pairs:
            print("No affordable trading pairs found with your investment amount. Continuing to next iteration.")
            continue
        multi_pair_coins = find_coins_with_multiple_pairs(affordable_pairs)
        if multi_pair_coins:
            affordable_units = calculate_affordable_units(investment_amount, multi_pair_coins)
            table_data = print_coins_with_multiple_pairs(multi_pair_coins, affordable_units, ticker_dict)
            liquid_coins = pre_filter_liquid_pairs(multi_pair_coins, ticker_dict)
            if not liquid_coins:
                print("\nNo liquid coins with multiple trading pairs found. Continuing to next iteration.")
                continue
            arbitrage_opportunities = find_best_triangular_arbitrage(liquid_coins, investment_amount, ticker_dict)
            print_arbitrage_paths(arbitrage_opportunities)
            if arbitrage_opportunities:
                realistic_opportunities = [opp for opp in arbitrage_opportunities if opp['profit'] > 0]
                if realistic_opportunities:
                    best_realistic = max(realistic_opportunities, key=lambda x: x['profit'])
                    profit_percentage = (best_realistic['profit'] / investment_amount) * 100
                    print(f"\n{Fore.GREEN}Best Realistic Triangular Arbitrage (Highest Profit):{Style.RESET_ALL}")
                    print(f"  Initial Amount: {investment_amount:.6f} USDT")
                    print(f"  Coin: {best_realistic['coin']}, Potential Profit: {best_realistic['profit']:.6f} USDT "
                          f"({profit_percentage:.2f}% after {TRADING_FEE * 100}% fees per trade)")
                    print(f"  Path: {best_realistic['path']}")
                    print(f"  Units of {best_realistic['coin']} Affordable: {best_realistic['units']:.6f}")
                else:
                    print(f"\n{Fore.YELLOW}No profitable arbitrage opportunities found among liquid coins. Showing best possible path:{Style.RESET_ALL}")
                    best_opportunity = arbitrage_opportunities[0]
                    profit_percentage = (best_opportunity['profit'] / investment_amount) * 100
                    print(f"  Initial Amount: {investment_amount:.6f} USDT")
                    print(f"  Coin: {best_opportunity['coin']}, Potential Profit: {best_opportunity['profit']:.6f} USDT "
                          f"({profit_percentage:.2f}% after {TRADING_FEE * 100}% fees per trade)")
                    print(f"  Path: {best_opportunity['path']}")
                    print(f"  Units of {best_opportunity['coin']} Affordable: {best_opportunity['units']:.6f}")
            else:
                print("\nNo triangular arbitrage opportunities found among liquid coins. Continuing to next iteration.")
                continue
            print(f"\n{Fore.YELLOW}Your Account Balances:{Style.RESET_ALL}")
            for currency, amount in balances.items():
                print(f"  {currency}: {amount:.6f}")
            usdt_balance = balances.get('USDT', 0)
            if usdt_balance < investment_amount:
                print(f"\n{Fore.RED}Error: Insufficient USDT balance ({usdt_balance:.6f} < {investment_amount:.6f}){Style.RESET_ALL}")
                continue
            if realistic_opportunities:
                print(f"\n{Fore.GREEN}Automatically executing best profitable trade...{Style.RESET_ALL}")
                success, execution_time, actual_profit, amount_used = execute_triangular_trade(
                    best_realistic['path'], best_realistic['units'], ticker_dict, usdt_balance, precisions)
                if success:
                    actual_profit_percentage = (actual_profit / amount_used) * 100
                    print(f"\n{ForeGREEN}Trade Results:{Style.RESET_ALL}")
                    print(f"  Path Followed: {best_realistic['path']}")
                    print(f"  Time Taken: {execution_time:.4f} seconds")
                    print(f"  Actual Profit: {actual_profit:.6f} USDT")
                    print(f"  Actual Profit Percentage: {actual_profit_percentage:.2f}%")
                    print("Trade completed successfully! Check your KuCoin account.")
                else:
                    print(f"\n{Fore.RED}Trade failed. Please check the error above.{Style.RESET_ALL}")
            else:
                print("\nNo profitable opportunities available to execute among liquid coins.")
        else:
            print("\nNo coins with multiple trading pairs (including major coins and USDT) found. Continuing to next iteration.")
            continue
        end_time = time.time()
        total_time = end_time - start_time
        print(f"{Fore.MAGENTA}Total time taken for this iteration: {total_time:.4f} seconds{Style.RESET_ALL}")

if __name__ == "__main__":
    main()