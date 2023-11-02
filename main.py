from aiohttp import ClientResponseError,ClientError
from collections import defaultdict
from colorama import Fore, init,Style
from dateutil import parser
import pandas as pd
import pyfiglet
import aiohttp
import asyncio
import json
import sys

# Initialize colorama to auto-reset after each print
init(autoreset=True)


def load_wallets_from_file(file_path: str = "wallets.txt", default_content: list = None) -> list:
    try:
        with open(file_path, 'r') as file:
            wallets = file.read().strip().split('\n')
            # Filter out any empty strings in case there are blank lines
            wallets = [wallet for wallet in wallets if wallet]
    except FileNotFoundError:
        # Create the file if it doesn't exist and populate with default content if provided
        print(f"{Fore.YELLOW}Warning: '{file_path}' not found. Creating a new file.")
        with open(file_path, 'w') as file:
            if default_content:
                for wallet in default_content:
                    file.write(wallet + '\n')
            wallets = default_content or []
    return wallets

def create_script_logo():
    ascii_art = pyfiglet.figlet_format("$JUP aid")
    print(Fore.BLUE + ascii_art)

# Function to sort the wallet data and return it as a pandas DataFrame
def sort_wallet_data(wallet_data: dict) -> pd.DataFrame:
    # Construct the lists for the DataFrame
    data = {
        'Wallet': [wallet_id for wallet_id in wallet_data],
        'Total': [sum(details.get('total', 0) for details in years.values()) for years in wallet_data.values()],
        'Operations': [sum(details.get('operations', 0) for details in years.values()) for years in wallet_data.values()],
        'Years': [','.join(map(str, years.keys())) for years in wallet_data.values()]
    }

    # Create and sort the DataFrame
    df_sorted = pd.DataFrame(data).sort_values(by=['Total', 'Operations'], ascending=[False, False], ignore_index=True)
    return df_sorted


# Function to print wallet qualifications
def print_wallet_qualification(df: pd.DataFrame) -> None:
    for _, row in df.iterrows():
        total_volume = row['Total']
        if total_volume > 0:
            generic_info = f"{Fore.GREEN}Wallet {row['Wallet']} qualifies for $JUP | "
            specific_info = f"{row['Operations']} operations detected and {total_volume}$ volume detected."
            print(f"{generic_info}{specific_info}")
        else:
            print(f"{Fore.RED}Wallet {row['Wallet']} does not qualify for $JUP | No operations detected.")


# Asynchronous function to fetch Jup transactions for a wallet
async def fetch_jup_transactions(wallet: str, session: aiohttp.ClientSession, retries: int = 3) -> json:
    url = 'https://stats.jup.ag/transactions'
    params = {'publicKey': wallet}
    headers = {'Accept': 'application/json'}
    
    for attempt in range(retries):
        try:
            async with session.get(url, params=params, headers=headers) as response:
                response.raise_for_status()  # will raise an HTTPError if the HTTP request returned an unsuccessful status code
                return await response.json()
        except ClientResponseError as e:
            if e.status == 403:
                print(f"{Fore.RED} Attempt {attempt + 1} of {retries}: Access to the Jup API was forbidden. Retrying...")
                await asyncio.sleep(2)  # wait for 2 seconds before retrying
            else:
                raise  # re-raise the exception if it's not a 403 Forbidden
        except ClientError as e:
            print(f"{Fore.RED} Attempt {attempt + 1} of {retries}: An error occurred: {e}")
            await asyncio.sleep(2)  # wait for 2 seconds before retrying
    raise Exception(f"All {retries} attempts to fetch data from the Jup API have failed.")


# Function to fetch transaction information
def fetch_transaction_information(transactions: list[dict]) -> list:
    wallet_swap_details = []
    for tx in transactions:
        swap_date = tx.get("timestamp")
        parsed_date = parser.isoparse(swap_date)
        tx_year = parsed_date.year
        tx_in_usd_value = round(float(tx.get("inAmountInUSD")), 2)
        wallet_swap_details.append((tx_year, tx_in_usd_value))
    return wallet_swap_details


# Function to summarize transactions
def summarize_transactions(transactions: list[tuple]) -> dict:
    summary = defaultdict(lambda: {'operations': 0, 'total': 0.0})
    for year, amount in transactions:
        summary[year]['operations'] += 1
        summary[year]['total'] += amount
    return dict(summary)


# Main asynchronous function
async def main(wallets: list) -> None:
    wallets_jup_swap_info = {}
    
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_jup_transactions(wallet, session) for wallet in wallets]
        transaction_results = await asyncio.gather(*tasks)
        
        for wallet, transactions in zip(wallets, transaction_results):
            wallet_swap_details = fetch_transaction_information(transactions)
            wallets_jup_swap_info[wallet] = summarize_transactions(wallet_swap_details)
    
    sorted_data = sort_wallet_data(wallet_data=wallets_jup_swap_info)
    print_wallet_qualification(df=sorted_data)


if __name__ == "__main__":
    # Check for Windows platform to set the event loop policy for asyncio
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    create_script_logo()
    wallets = load_wallets_from_file()
    if wallets:
        asyncio.run(main(wallets))
    else:
        print(f"{Fore.YELLOW} Warning: 'wallets.txt' is empty. Please provide your wallet addresses in the file.")
        
    
