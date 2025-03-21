import time
from kucoin.client import Market, User, Trade
from colorama import init, Fore, Style
from tabulate import tabulate

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
LIQUIDITY_THRESHOLD = 100000


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
            else:
                print(f"Warning: Missing required keys in symbol data: {symbol}")
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


def find_affordable_pairs(investment_amount, ticker_dict):
    affordable_pairs = []
    for symbol, ticker_data in ticker_dict.items():
        last_price = ticker_data['last']
        if last_price > 0 and investment_amount >= last_price:
            base, quote = symbol.split('-')
            affordable_pairs.append({
                'symbol': symbol,
                'price': last_price,
                'base_currency': base,
                'quote_currency': quote
            })
    return affordable_pairs


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

        volume_usd = 0
        for pair in pairs:
            symbol = pair['symbol']
            if symbol in ticker_dict:
                volume_usd += ticker_dict[symbol].get('volValue', 0)

        liquidity_status = f"{Fore.GREEN}Liquid{Style.RESET_ALL}" if volume_usd >= LIQUIDITY_THRESHOLD else f"{Fore.RED}Illiquid{Style.RESET_ALL}"

        table.append([coin, pairs_str, units_str, f"{volume_usd:.2f}", liquidity_status])

    print(f"\n{Fore.BLUE}Coins with Multiple Trading Pairs:{Style.RESET_ALL}")
    print(tabulate(table, headers=headers, tablefmt="pretty"))
    return table


def find_best_triangular_arbitrage(multi_pair_coins, investment_amount, ticker_dict, fee_rate=TRADING_FEE):
    arbitrage_opportunities = []
    for coin, pairs in multi_pair_coins.items():
        volume_usd = 0
        for pair in pairs:
            symbol = pair['symbol']
            if symbol in ticker_dict:
                volume_usd += ticker_dict[symbol].get('volValue', 0)

        if volume_usd < LIQUIDITY_THRESHOLD:
            continue

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
        units_str = f"{units_adjusted:.{precision1['quantityPrecision']}f}"
        amount_usdt_str = f"{amount_usdt_rounded:.{precision1['pricePrecision']}f}"
        print(f"Debug: Using {amount_usdt_str} USDT to buy {units_str} {base1} (price: {price1})")
        order1 = trade_client.create_market_order(pair1, 'buy', funds=amount_usdt_str)
        print(f"Step 1: Bought {units_str} {base1} with {amount_usdt_str} USDT - Order ID: {order1['orderId']}")

        balances = get_account_balances()
        available_base1 = balances.get(base1, 0)
        print(f"Debug: Available {base1} balance after Step 1: {available_base1}")
        if available_base1 < units_adjusted:
            units_adjusted = available_base1
            print(f"Warning: Adjusted units to available balance: {units_adjusted}")

        pair2 = steps[1]
        base2, quote2 = pair2.split('-')
        precision2 = precisions.get(pair2, {'quantityPrecision': 2, 'pricePrecision': 2, 'baseMinSize': 0.1})
        units_str = f"{units_adjusted:.{precision2['quantityPrecision']}f}"
        if units_adjusted < precision2['baseMinSize']:
            print(f"Error: Units {units_adjusted:.6f} {base2} below minimum {precision2['baseMinSize']} for {pair2}")
            return False, 0, 0, 0
        if units_adjusted <= 0:
            print(f"Error: No {base2} available to sell after Step 1")
            return False, 0, 0, 0
        print(f"Debug: Selling {units_str} {base2} for {quote2}")
        order2 = trade_client.create_market_order(pair2, 'sell', size=units_str)
        print(f"Step 2: Sold {units_str} {base2} for {quote2} - Order ID: {order2['orderId']}")

        balances = get_account_balances()
        available_quote2 = balances.get(quote2, 0)
        print(f"Debug: Available {quote2} balance after Step 2: {available_quote2}")
        if available_quote2 <= 0:
            print(f"Error: No {quote2} available to sell after Step 2")
            return False, 0, 0, 0

        pair3 = steps[2]
        price3 = ticker_dict.get(pair3, {}).get('last', float('inf'))
        if price3 == float('inf'):
            print(f"Error: No price found for {pair3}")
            return False, 0, 0, 0
        precision3 = precisions.get(pair3, {'quantityPrecision': 8, 'pricePrecision': 2, 'baseMinSize': 0.00001})
        acquired_units = available_quote2
        if acquired_units < precision3['baseMinSize']:
            print(f"Error: {quote2} amount {acquired_units:.8f} below minimum {precision3['baseMinSize']} for {pair3}")
            return False, 0, 0, 0
        if acquired_units * price3 < MIN_ORDER_SIZE:
            print(
                f"Error: {quote2} value {acquired_units:.8f} * {price3} = {acquired_units * price3:.6f} USDT below minimum {MIN_ORDER_SIZE} USDT")
            return False, 0, 0, 0
        acquired_units_str = f"{acquired_units:.{precision3['quantityPrecision']}f}"
        if float(acquired_units_str) <= 0:
            print(f"Error: Invalid quantity {acquired_units_str} {quote2} after rounding")
            return False, 0, 0, 0
        print(f"Debug: Selling {acquired_units_str} {quote2} back to USDT")
        order3 = trade_client.create_market_order(pair3, 'sell', size=acquired_units_str)
        print(f"Step 3: Sold {acquired_units_str} {quote2} back to USDT - Order ID: {order3['orderId']}")

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
    precisions = get_symbol_precisions()
    if not precisions:
        print(
            f"{Fore.YELLOW}Warning: Using default precision and minimums (2 for most, 8/0.00001 for BTC) due to fetch failure.{Style.RESET_ALL}")
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

        # Start timing after user input
        start_time = time.time()
        try:
            print(f"\nFetching affordable trading pairs for {investment_amount:.6f} USDT...\n")

            all_tickers = get_all_tickers()
            if not all_tickers:
                print("Failed to fetch ticker data. Continuing to next iteration.")
                continue
            ticker_dict = {}
            for ticker in all_tickers:
                try:
                    if ticker['last'] is not None:
                        ticker_dict[ticker['symbol']] = {
                            'last': float(ticker['last']),
                            'volValue': float(ticker['volValue'])
                        }
                    else:
                        print(f"Warning: Skipping {ticker['symbol']} due to missing price data")
                except (ValueError, TypeError) as e:
                    print(f"Warning: Skipping {ticker['symbol']} due to invalid price data: {e}")

            if not ticker_dict:
                print("No valid ticker data available. Continuing to next iteration.")
                continue

            affordable_pairs = find_affordable_pairs(investment_amount, ticker_dict)
            if not affordable_pairs:
                print("No affordable trading pairs found with your investment amount. Continuing to next iteration.")
                continue

            print(f"{Fore.WHITE}Affordable Trading Pairs:{Style.RESET_ALL}")
            for pair in affordable_pairs:
                print(f"  {pair['symbol']} - Last Price: {pair['price']:.6f} USDT")

            multi_pair_coins = find_coins_with_multiple_pairs(affordable_pairs)
            if multi_pair_coins:
                affordable_units = calculate_affordable_units(investment_amount, multi_pair_coins)
                table_data = print_coins_with_multiple_pairs(multi_pair_coins, affordable_units, ticker_dict)

                liquid_coins = {
                    row[0]: multi_pair_coins[row[0]]
                    for row in table_data
                    if "Liquid" in row[4]
                }

                if not liquid_coins:
                    print("\nNo liquid coins with multiple trading pairs found. Continuing to next iteration.")
                    continue

                arbitrage_opportunities = find_best_triangular_arbitrage(
                    liquid_coins, investment_amount, ticker_dict
                )

                print_arbitrage_paths(arbitrage_opportunities)

                if arbitrage_opportunities:
                    realistic_opportunities = [opp for opp in arbitrage_opportunities if opp['profit'] > 0]
                    if realistic_opportunities:
                        best_realistic = max(realistic_opportunities, key=lambda x: x['profit'])
                        profit_percentage = (best_realistic['profit'] / investment_amount) * 100
                        print(f"\n{Fore.GREEN}Best Realistic Triangular Arbitrage (Highest Profit):{Style.RESET_ALL}")
                        print(f"  Initial Amount: {investment_amount:.6f} USDT")
                        print(
                            f"  Coin: {best_realistic['coin']}, Potential Profit: {best_realistic['profit']:.6f} USDT "
                            f"({profit_percentage:.2f}% after {TRADING_FEE * 100}% fees per trade)")
                        print(f"  Path: {best_realistic['path']}")
                        print(f"  Units of {best_realistic['coin']} Affordable: {best_realistic['units']:.6f}")
                    else:
                        print(
                            f"\n{Fore.YELLOW}No profitable arbitrage opportunities found among liquid coins. Showing best possible path:{Style.RESET_ALL}")
                        best_opportunity = arbitrage_opportunities[0]
                        profit_percentage = (best_opportunity['profit'] / investment_amount) * 100
                        print(f"  Initial Amount: {investment_amount:.6f} USDT")
                        print(
                            f"  Coin: {best_opportunity['coin']}, Potential Profit: {best_opportunity['profit']:.6f} USDT "
                            f"({profit_percentage:.2f}% after {TRADING_FEE * 100}% fees per trade)")
                        print(f"  Path: {best_opportunity['path']}")
                        print(f"  Units of {best_opportunity['coin']} Affordable: {best_opportunity['units']:.6f}")
                else:
                    print(
                        "\nNo triangular arbitrage opportunities found among liquid coins. Continuing to next iteration.")
                    continue

                balances = get_account_balances()
                print(f"\n{Fore.YELLOW}Your Account Balances:{Style.RESET_ALL}")
                for currency, amount in balances.items():
                    print(f"  {currency}: {amount:.6f}")

                usdt_balance = balances.get('USDT', 0)
                if usdt_balance < investment_amount:
                    print(
                        f"\n{Fore.RED}Error: Insufficient USDT balance ({usdt_balance:.6f} < {investment_amount:.6f}){Style.RESET_ALL}")
                    continue

                if realistic_opportunities:
                    print(f"\n{Fore.GREEN}Automatically executing best profitable trade...{Style.RESET_ALL}")
                    success, execution_time, actual_profit, amount_used = execute_triangular_trade(
                        best_realistic['path'], best_realistic['units'], ticker_dict, usdt_balance, precisions)
                    if success:
                        actual_profit_percentage = (actual_profit / amount_used) * 100
                        print(f"\n{Fore.GREEN}Trade Results:{Style.RESET_ALL}")
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
                print(
                    "\nNo coins with multiple trading pairs (including major coins and USDT) found. Continuing to next iteration.")
                continue

            print(f"\n{Fore.CYAN}Process complete. Ready for next investment.{Style.RESET_ALL}")

        finally:
            end_time = time.time()
            total_time = end_time - start_time
            print(f"{Fore.MAGENTA}Total time taken for this iteration: {total_time:.4f} seconds{Style.RESET_ALL}")


if __name__ == "__main__":
    main()