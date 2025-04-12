import time
from binance.client import Client
from binance.enums import *
from colorama import init, Fore, Style
from tabulate import tabulate
from functools import lru_cache
from threading import Lock

init()

API_KEY = "WKmQGICyNTHE6hyfIIkK3KW4P8MbenYrX4BuopEMtktFbS6mtiXpappeWk0mjmwH"
API_SECRET = "4kc2SzuKVQLx7ifWjfEbPMApLwWwG939TFnnEb4Wn36VTi8rVP25NHpBdekpPTAc"

client = Client(API_KEY, API_SECRET)
MAJOR_COINS = {'BTC', 'ETH', 'BNB', 'XRP', 'USDT', 'USDC'}
TRADING_FEE = 0.001  # Binance spot trading fee (0.1%)
MIN_ORDER_SIZE = 10  # Binance minimum order size in USD
LIQUIDITY_THRESHOLD = 100000

# Cache storage for balances
_balances_cache = {}
_cache_timestamp = 0
_cache_ttl = 5  # Cache TTL in seconds
_cache_lock = Lock()


def get_symbol_precisions():
    start_time = time.time()
    try:
        exchange_info = client.get_exchange_info()
        precision_dict = {}
        for symbol in exchange_info['symbols']:
            precision_dict[symbol['symbol']] = {
                'quantityPrecision': symbol['quantityPrecision'],
                'pricePrecision': symbol['pricePrecision'],
                'baseMinSize': float(symbol['filters'][2]['minQty'])  # LOT_SIZE filter
            }
        print(f"Time taken for get_symbol_precisions: {time.time() - start_time:.4f} seconds")
        return precision_dict
    except Exception as e:
        print(f"Error fetching symbol precisions: {e}")
        return {}


def get_all_tickers():
    start_time = time.time()
    try:
        tickers = client.get_ticker()
        print(f"Time taken for get_all_tickers: {time.time() - start_time:.4f} seconds")
        return tickers
    except Exception as e:
        print(f"Error fetching tickers: {e}")
        return []


def get_account_balances(force_refresh=False):
    global _balances_cache, _cache_timestamp
    start_time = time.time()

    with _cache_lock:
        current_time = time.time()
        if not force_refresh and _balances_cache and (current_time - _cache_timestamp < _cache_ttl):
            print(f"Time taken for get_account_balances (cached): {time.time() - start_time:.4f} seconds")
            return _balances_cache.copy()

        try:
            account = client.get_account()
            balances = {
                asset['asset']: float(asset['free'])
                for asset in account['balances']
                if float(asset['free']) > 0
            }
            _balances_cache = balances
            _cache_timestamp = current_time
            print(f"Time taken for get_account_balances: {time.time() - start_time:.4f} seconds")
            return balances.copy()
        except Exception as e:
            print(f"Error fetching balances: {e}")
            return _balances_cache.copy() if _balances_cache else {}


def find_affordable_pairs(investment_amount, ticker_dict):
    start_time = time.time()
    affordable_pairs = []
    for ticker in ticker_dict:
        symbol = ticker['symbol']
        last_price = float(ticker['lastPrice'])
        if last_price > 0 and investment_amount >= last_price:
            base = symbol[:-4] if symbol.endswith('USDT') else symbol[:-3]  # Assumes quote is 3-4 chars
            quote = 'USDT' if symbol.endswith('USDT') else symbol[-3:]
            affordable_pairs.append({
                'symbol': symbol,
                'price': last_price,
                'base_currency': base,
                'quote_currency': quote
            })
    print(f"Time taken for find_affordable_pairs: {time.time() - start_time:.4f} seconds")
    return affordable_pairs


def find_coins_with_multiple_pairs(affordable_pairs):
    start_time = time.time()
    base_currency_count = {}
    base_currency_pairs = {}
    for pair in affordable_pairs:
        base = pair['base_currency']
        base_currency_count[base] = base_currency_count.get(base, 0) + 1
        base_currency_pairs.setdefault(base, []).append(pair)

    multi_pair_coins = {}
    for base, count in base_currency_count.items():
        if count > 1:
            pairs = base_currency_pairs[base]
            has_major_pair = any(pair['quote_currency'] in MAJOR_COINS for pair in pairs)
            has_usdt_pair = any(pair['quote_currency'] == 'USDT' for pair in pairs)
            if has_major_pair and has_usdt_pair:
                multi_pair_coins[base] = pairs
    print(f"Time taken for find_coins_with_multiple_pairs: {time.time() - start_time:.4f} seconds")
    return multi_pair_coins


def calculate_affordable_units(investment_amount, multi_pair_coins):
    start_time = time.time()
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
    print(f"Time taken for calculate_affordable_units: {time.time() - start_time:.4f} seconds")
    return affordable_units


def print_coins_with_multiple_pairs(multi_pair_coins, affordable_units, ticker_dict):
    start_time = time.time()
    table = []
    headers = ["Coin", "Pairs", "Affordable Units (USDT)", "24h Volume (USD)", "Liquidity"]
    for coin, pairs in multi_pair_coins.items():
        pairs_str = ", ".join(pair['symbol'] for pair in pairs)
        units_info = affordable_units.get(coin, {})
        units_str = ", ".join(f"{symbol}: {units:.6f}" for symbol, units in units_info.items())

        volume_usd = sum(float(t['quoteVolume']) for t in ticker_dict
                         if t['symbol'] in [p['symbol'] for p in pairs])

        liquidity_status = f"{Fore.GREEN}Liquid{Style.RESET_ALL}" if volume_usd >= LIQUIDITY_THRESHOLD else f"{Fore.RED}Illiquid{Style.RESET_ALL}"
        table.append([coin, pairs_str, units_str, f"{volume_usd:.2f}", liquidity_status])

    print(f"\n{Fore.BLUE}Coins with Multiple Trading Pairs:{Style.RESET_ALL}")
    print(tabulate(table, headers=headers, tablefmt="pretty"))
    print(f"Time taken for print_coins_with_multiple_pairs: {time.time() - start_time:.4f} seconds")
    return table


def find_best_triangular_arbitrage(multi_pair_coins, investment_amount, ticker_dict, fee_rate=TRADING_FEE):
    start_time = time.time()
    arbitrage_opportunities = []
    ticker_dict_map = {t['symbol']: t for t in ticker_dict}

    for coin, pairs in multi_pair_coins.items():
        volume_usd = sum(float(t['quoteVolume']) for t in ticker_dict
                         if t['symbol'] in [p['symbol'] for p in pairs])
        if volume_usd < LIQUIDITY_THRESHOLD:
            continue

        usdt_pair = next((p for p in pairs if p['quote_currency'] == 'USDT'), None)
        major_coin_pairs = [p for p in pairs if p['quote_currency'] in MAJOR_COINS and p['quote_currency'] != 'USDT']

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
            major_to_usdt_symbol = f"{major_coin}USDT"
            major_to_usdt_price = float(ticker_dict_map.get(major_to_usdt_symbol, {}).get('lastPrice', 0)) / 1.005
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
    print(f"Time taken for find_best_triangular_arbitrage: {time.time() - start_time:.4f} seconds")
    return arbitrage_opportunities


def print_arbitrage_paths(arbitrage_opportunities):
    start_time = time.time()
    table = []
    headers = ["Coin", "Profit (USDT)", "Path", "Affordable Units"]
    for opp in arbitrage_opportunities:
        profit_color = Fore.GREEN if opp['profit'] > 0 else Fore.RED
        profit_str = f"{profit_color}{opp['profit']:.6f}{Style.RESET_ALL}"
        table.append([opp['coin'], profit_str, opp['path'], f"{opp['units']:.6f}"])
    print(f"\n{Fore.CYAN}Triangular Arbitrage Paths:{Style.RESET_ALL}")
    print(tabulate(table, headers=headers, tablefmt="pretty"))
    print(f"Time taken for print_arbitrage_paths: {time.time() - start_time:.4f} seconds")


def execute_triangular_trade(path, units, ticker_dict, initial_usdt, precisions):
    try:
        start_time = time.time()
        steps = path.split(' -> ')
        ticker_dict_map = {t['symbol']: t for t in ticker_dict}
        print(f"\nExecuting trade: {path} with {units:.6f} units")

        # Step 1: Buy base with USDT
        pair1 = steps[0]
        price1 = float(ticker_dict_map.get(pair1, {}).get('lastPrice', 0))
        precision1 = precisions.get(pair1, {'quantityPrecision': 2, 'pricePrecision': 2, 'baseMinSize': 0.1})
        amount_usdt = units * price1
        if amount_usdt < MIN_ORDER_SIZE:
            print(f"Error: Initial funds {amount_usdt:.6f} USDT below minimum {MIN_ORDER_SIZE} USDT")
            return False, 0, 0, 0

        qty1 = round(units, precision1['quantityPrecision'])
        order1 = client.order_market_buy(symbol=pair1, quantity=qty1)
        print(f"Step 1: Bought {qty1} {pair1[:-4]} with USDT - Order ID: {order1['orderId']}")

        # Step 2: Sell base for major coin
        pair2 = steps[1]
        precision2 = precisions.get(pair2, {'quantityPrecision': 2, 'pricePrecision': 2, 'baseMinSize': 0.1})
        order2 = client.order_market_sell(symbol=pair2, quantity=qty1)
        print(f"Step 2: Sold {qty1} {pair2[:-3]} for {pair2[-3:]} - Order ID: {order2['orderId']}")

        # Step 3: Sell major coin for USDT
        pair3 = steps[2]
        precision3 = precisions.get(pair3, {'quantityPrecision': 2, 'pricePrecision': 2, 'baseMinSize': 0.1})
        balances = get_account_balances(force_refresh=True)
        major_coin = pair3[:-4]
        qty3 = round(balances.get(major_coin, 0), precision3['quantityPrecision'])
        if qty3 <= 0:
            print(f"Error: No {major_coin} available to sell")
            return False, 0, 0, 0
        order3 = client.order_market_sell(symbol=pair3, quantity=qty3)
        print(f"Step 3: Sold {qty3} {major_coin} back to USDT - Order ID: {order3['orderId']}")

        final_balances = get_account_balances(force_refresh=True)
        final_usdt = final_balances.get('USDT', 0)
        profit = final_usdt - (initial_usdt - amount_usdt)

        execution_time = time.time() - start_time
        print(f"Total time taken for execute_triangular_trade: {execution_time:.4f} seconds")
        return True, execution_time, profit, amount_usdt
    except Exception as e:
        print(f"Error executing trade: {e}")
        return False, 0, 0, 0


def main():
    precisions = get_symbol_precisions()
    if not precisions:
        print(f"{Fore.YELLOW}Warning: Using default precisions due to fetch failure.{Style.RESET_ALL}")

    while True:
        investment_amount = float(input("How much do you want to invest (in USDT)? "))
        if investment_amount < MIN_ORDER_SIZE:
            print(f"Investment must be at least {MIN_ORDER_SIZE} USDT.")
            continue

        start_time = time.time()
        all_tickers = get_all_tickers()
        ticker_dict = [t for t in all_tickers if float(t['lastPrice']) > 0]

        affordable_pairs = find_affordable_pairs(investment_amount, ticker_dict)
        multi_pair_coins = find_coins_with_multiple_pairs(affordable_pairs)

        if multi_pair_coins:
            affordable_units = calculate_affordable_units(investment_amount, multi_pair_coins)
            table_data = print_coins_with_multiple_pairs(multi_pair_coins, affordable_units, ticker_dict)

            liquid_coins = {row[0]: multi_pair_coins[row[0]] for row in table_data if "Liquid" in row[4]}
            if liquid_coins:
                arbitrage_opportunities = find_best_triangular_arbitrage(liquid_coins, investment_amount, ticker_dict)
                print_arbitrage_paths(arbitrage_opportunities)

                if arbitrage_opportunities and any(opp['profit'] > 0 for opp in arbitrage_opportunities):
                    best_opp = max([opp for opp in arbitrage_opportunities if opp['profit'] > 0],
                                   key=lambda x: x['profit'])
                    balances = get_account_balances()
                    if balances.get('USDT', 0) >= investment_amount:
                        success, exec_time, profit, amount_used = execute_triangular_trade(
                            best_opp['path'], best_opp['units'], ticker_dict, balances['USDT'], precisions
                        )
                        if success:
                            print(f"Trade completed: Profit {profit:.6f} USDT in {exec_time:.4f} seconds")

        print(f"Total time taken: {time.time() - start_time:.4f} seconds")


if __name__ == "__main__":
    main()