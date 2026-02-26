"""
Сервисы для получения рыночных данных: Fear & Greed, деривативы, он-чейн, макро, институции и т.д.
"""

from .fear_greed import get_fear_greed_index
from .derivatives import get_btc_derivatives
from .onchain import get_btc_onchain
from .macro import get_macro_data
from .institutions import get_btc_institutions
from .sentiment import get_btc_sentiment

__all__ = [
    'get_fear_greed_index', 'get_btc_derivatives', 'get_btc_onchain',
    'get_macro_data', 'get_btc_institutions', 'get_btc_sentiment',
]
