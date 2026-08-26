from unittest.mock import MagicMock, patch

import pytest

from app.services.stock_service import StockService
from app.utils.errors import NoDataFoundError


@pytest.mark.asyncio
async def test_get_quote_yfinance_success():
    fake_info = {
        "currentPrice": 150.0,
        "previousClose": 145.0,
        "currency": "USD",
        "dayHigh": 151.0,
        "dayLow": 148.0,
        "volume": 1_000_000,
        "marketCap": 2_500_000_000_000,
    }
    with patch("app.services.stock_service.yf.Ticker") as mock_ticker_cls:
        mock_ticker = MagicMock()
        mock_ticker.get_info.return_value = fake_info
        mock_ticker_cls.return_value = mock_ticker

        service = StockService()
        quote = await service.get_quote("AAPLTEST1")

        assert quote.provider == "yfinance"
        assert quote.price == 150.0
        assert quote.change == 5.0
        assert round(quote.change_percent, 2) == round(5.0 / 145.0 * 100, 2)


@pytest.mark.asyncio
async def test_get_quote_unknown_ticker_raises_not_found():
    with patch("app.services.stock_service.yf.Ticker") as mock_ticker_cls, patch(
        "app.services.stock_service.get_settings"
    ) as mock_get_settings:
        settings = MagicMock()
        settings.stock_data_primary_provider = "yfinance"
        settings.polygon_api_key = ""
        mock_get_settings.return_value = settings

        mock_ticker = MagicMock()
        mock_ticker.get_info.return_value = {}
        mock_ticker_cls.return_value = mock_ticker

        service = StockService()
        with pytest.raises(NoDataFoundError):
            await service.get_quote("NOPE_TICKER_2")
