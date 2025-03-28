# cythonintegration/arbitrage_logic.pyx
cimport cython
from libc.stdlib cimport malloc, free

# Constants
cdef double TRADING_FEE = 0.001
cdef double MIN_ORDER_SIZE = 0.1
cdef double LIQUIDITY_THRESHOLD = 100000
cdef set MAJOR_COINS = {'BTC', 'ETH', 'KCS', 'BNB', 'XRP', 'USDC'}

@cython.boundscheck(False)
@cython.wraparound(False)
cpdef list find_affordable_pairs(double investment_amount, dict ticker_dict):
    cdef list affordable_pairs = []
    cdef str symbol, base, quote
    cdef double last_price
    cdef dict pair_data, ticker_data

    for symbol, ticker_data in ticker_dict.items():
        last_price = ticker_data['last']
        if last_price > 0 and investment_amount >= last_price:
            base, quote = symbol.split('-')
            pair_data = {
                'symbol': symbol,
                'price': last_price,
                'base_currency': base,
                'quote_currency': quote
            }
            affordable_pairs.append(pair_data)
    return affordable_pairs

@cython.boundscheck(False)
@cython.wraparound(False)
cpdef dict find_coins_with_multiple_pairs(list affordable_pairs):
    cdef dict base_currency_count = {}
    cdef dict base_currency_pairs = {}
    cdef dict multi_pair_coins = {}
    cdef str base
    cdef int count
    cdef list pairs
    cdef dict pair
    cdef bint has_major_pair, has_usdt_pair

    for pair in affordable_pairs:
        base = pair['base_currency']
        if base in base_currency_count:
            base_currency_count[base] += 1
            base_currency_pairs[base].append(pair)
        else:
            base_currency_count[base] = 1
            base_currency_pairs[base] = [pair]

    for base, count in base_currency_count.items():
        if count > 1:
            pairs = base_currency_pairs[base]
            has_major_pair = False
            has_usdt_pair = False
            for pair in pairs:
                if pair['quote_currency'] in MAJOR_COINS:
                    has_major_pair = True
                if pair['quote_currency'] == 'USDT':
                    has_usdt_pair = True
            if has_major_pair and has_usdt_pair:
                multi_pair_coins[base] = pairs

    return multi_pair_coins

@cython.boundscheck(False)
@cython.wraparound(False)
cpdef dict calculate_affordable_units(double investment_amount, dict multi_pair_coins):
    cdef dict affordable_units = {}
    cdef dict units_per_pair
    cdef str coin, symbol
    cdef list pairs
    cdef dict pair
    cdef double price, units

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

@cython.boundscheck(False)
@cython.wraparound(False)
cpdef list find_best_triangular_arbitrage(dict multi_pair_coins, double investment_amount, dict ticker_dict, double fee_rate=TRADING_FEE):
    cdef list arbitrage_opportunities = []
    cdef str coin, symbol, major_coin, path, major_to_usdt_symbol
    cdef dict pairs, pair, usdt_pair, opp
    cdef list major_coin_pairs
    cdef double volume_usd, usdt_price, units_x, amount_x, x_to_major_price, units_major, amount_major, major_to_usdt_price, final_usdt, profit

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

        for pair in major_coin_pairs:
            usdt_price = usdt_pair['price'] * 1.005
            units_x = investment_amount / usdt_price
            amount_x = units_x * (1 - fee_rate)
            major_coin = pair['quote_currency']
            x_to_major_price = pair['price'] / 1.005
            units_major = amount_x * x_to_major_price
            amount_major = units_major * (1 - fee_rate)
            major_to_usdt_symbol = f"{major_coin}-USDT"
            major_to_usdt_price = ticker_dict.get(major_to_usdt_symbol, {}).get('last', 0) / 1.005
            if major_to_usdt_price == 0:
                continue
            final_usdt = amount_major * major_to_usdt_price * (1 - fee_rate)
            profit = final_usdt - investment_amount
            path = f"{usdt_pair['symbol']} -> {pair['symbol']} -> {major_to_usdt_symbol}"
            opp = {'coin': coin, 'profit': profit, 'path': path, 'units': units_x}
            arbitrage_opportunities.append(opp)

    arbitrage_opportunities.sort(key=lambda x: x['profit'], reverse=True)
    return arbitrage_opportunities if arbitrage_opportunities else []