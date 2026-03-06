import os
import logging
from dataclasses import dataclass

from alpaca.trading.client import TradingClient
from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.data.historical.stock import StockHistoricalDataClient

logger = logging.getLogger(__name__)


@dataclass
class AlpacaClients:
    trading: TradingClient
    options_data: OptionHistoricalDataClient
    stock_data: StockHistoricalDataClient


def get_clients(paper: bool = True) -> AlpacaClients:
    api_key = os.environ.get("ALPACA_API_KEY")
    secret_key = os.environ.get("ALPACA_SECRET_KEY")

    if not api_key or not secret_key:
        raise EnvironmentError(
            "ALPACA_API_KEY and ALPACA_SECRET_KEY must be set in environment / .env file"
        )

    trading = TradingClient(api_key, secret_key, paper=paper)
    options_data = OptionHistoricalDataClient(api_key, secret_key)
    stock_data = StockHistoricalDataClient(api_key, secret_key)

    logger.info(f"Alpaca clients initialized (paper={paper})")
    return AlpacaClients(trading=trading, options_data=options_data, stock_data=stock_data)
