import csv
import io
from urllib.request import urlopen
import yfinance as yf
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

class TestYfinanceIndexChange:
    # URL for S&P 500 constituents
    SP500_CSV_URL = (
        "https://jcoffi.github.io/index-constituents/constituents-sp500.csv"
    )

    def load_constituents(self, url: str):
        """Download the index CSV and return (symbol, name) tuples."""
        try:
            with urlopen(url) as response:
                reader = csv.DictReader(
                    io.TextIOWrapper(response, encoding="utf-8", newline="")
                )
                return [
                    (row["Symbol"].strip(), row.get("Name", "").strip())
                    for row in reader
                    if row.get("Symbol")
                ]
        except Exception as e:
            print(f"Error loading constituents from {url}: {e}")
            return []

    def analyze_index_changes(self, index_url: str, index_name: str):
        """
        Fetches constituents for a given index, downloads their price data,
        and calculates the distribution of positive, negative, and flat changes.
        """
        print(f"Fetching {index_name} constituents list...")
        constituents = self.load_constituents(index_url)
        
        if not constituents:
            print(f"Failed to load constituents for {index_name}.")
            return

        # 1. Prepare data & handle symbol corrections
        # Yahoo Finance uses '-' instead of '.' (e.g., BRK.B -> BRK-B)
        symbol_list = []
        name_map = {}
        
        for s, n in constituents:
            yf_symbol = s.replace('.', '-')  # Key correction step
            symbol_list.append(yf_symbol)
            name_map[yf_symbol] = n

        print(f"Batch downloading data for {len(symbol_list)} symbols from {index_name}...")
        
        # 2. Use yf.download for a single bulk request
        # period="5d" ensures we get the last two trading days regardless of the day of the week.
        df = yf.download(symbol_list, period="2d", group_by='ticker', progress=True, threads=True)

        up = down = flat = missing = 0
        
        print("-" * 75)
        print(f"{'SYMBOL':<8} {'NAME':<40} {'CHANGE'}")
        print("-" * 75)

        # 3. Iterate and calculate changes
        for symbol in symbol_list:
            try:
                # Check if data for the symbol exists in the DataFrame
                if symbol not in df.columns.levels[0]:
                    raise KeyError("Data not found for symbol")

                # Extract 'Close' prices and remove any NaNs
                closes = df[symbol]['Close'].dropna()

                if len(closes) < 2:
                    missing += 1
                    continue

                # Get the latest price and previous day's close
                curr_price = closes.iloc[-1]
                prev_close = closes.iloc[-2]

                # Calculate percentage change
                pct = ((curr_price - prev_close) / prev_close) * 100

                # Tally results
                if pct > 0:
                    up += 1
                elif pct < 0:
                    down += 1
                else:
                    flat += 1

                # Truncate long names for display
                display_name = (name_map[symbol][:38] + '..') if len(name_map[symbol]) > 38 else name_map[symbol]
                print(f"{symbol:<8} {display_name:<40} {pct:+.2f}%")

            except Exception:
                missing += 1

        # 4. Print summary
        total = up + down + flat
        if total == 0:
            print("No valid price data was found to generate a summary.")
            return

        print("-" * 75)
        print(f"{index_name} Summary (Regular Market Change):")
        print(f"Up:   {up} ({up / total * 100:.2f}%)")
        print(f"Down: {down} ({down / total * 100:.2f}%)")
        print(f"Flat: {flat} ({flat / total * 100:.2f}%)")
        print(f"Missing/Error: {missing}")

    def _fetch_realtime_change_for_symbol(self, symbol, name_map):
        """Helper to fetch real-time change for a single symbol."""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            change_pct = info.get('regularMarketChangePercent')

            if change_pct is None:
                return symbol, name_map.get(symbol, ''), None, 'missing'

            change_pct *= 100  # Convert to percentage
            status = 'up' if change_pct > 0 else 'down' if change_pct < 0 else 'flat'
            return symbol, name_map.get(symbol, ''), change_pct, status

        except Exception:
            return symbol, name_map.get(symbol, ''), None, 'missing'

    def analyze_index_realtime_change(self, index_url: str, index_name: str):
        """
        Fetches constituents and analyzes their real-time change using
        'regularMarketChangePercent' with multithreading.
        """
        print(f"\n{'='*75}")
        print(f"Fetching {index_name} constituents for REAL-TIME analysis...")
        print(f"{'='*75}\n")

        constituents = self.load_constituents(index_url)

        if not constituents:
            print(f"Failed to load constituents for {index_name}.")
            return

        symbol_list = [s.replace('.', '-') for s, n in constituents]
        name_map = {s.replace('.', '-'): n for s, n in constituents}

        up = down = flat = missing = 0
        results = []

        print("-" * 75)
        print(f"{'SYMBOL':<8} {'NAME':<40} {'REAL-TIME CHANGE'}")
        print("-" * 75)

        with ThreadPoolExecutor(max_workers=20) as executor:
            # Submit all tasks to the executor
            future_to_symbol = {
                executor.submit(self._fetch_realtime_change_for_symbol, symbol, name_map): symbol
                for symbol in symbol_list
            }
            
            # Process results as they complete
            for i, future in enumerate(as_completed(future_to_symbol)):
                symbol, name, change_pct, status = future.result()
                
                results.append((symbol, name, change_pct, status))

                # Simple progress indicator
                print(f"Progress: {i + 1}/{len(symbol_list)}", end='\r')

        # Sort results alphabetically by symbol for consistent order
        results.sort(key=lambda x: x[0])
        
        # Now print sorted results and tally counts
        for symbol, name, change_pct, status in results:
            if status == 'missing':
                missing += 1
                continue
            
            if status == 'up':
                up += 1
            elif status == 'down':
                down += 1
            else:
                flat += 1

            display_name = (name[:38] + '..') if len(name) > 38 else name
            print(f"{symbol:<8} {display_name:<40} {change_pct:+.2f}%")

        # Print summary
        total = up + down + flat
        if total == 0:
            print("\nNo valid real-time data was found to generate a summary.")
            return

        print("\n" + "-" * 75)
        print(f"{index_name} Summary (Real-Time Market Change):")
        print(f"Up:   {up} ({up / total * 100:.2f}%)")
        print(f"Down: {down} ({down / total * 100:.2f}%)")
        print(f"Flat: {flat} ({flat / total * 100:.2f}%)")
        print(f"Missing/Unavailable: {missing}")


def main():
    """Main entry point to run the analysis."""
    analyzer = TestYfinanceIndexChange()
    # Historical analysis (last two trading days)
    analyzer.analyze_index_changes(analyzer.SP500_CSV_URL, "S&P 500")
    
    # Real-time analysis (using current market change)
    # analyzer.analyze_index_realtime_change(analyzer.SP500_CSV_URL, "S&P 500")

if __name__ == "__main__":
    main()