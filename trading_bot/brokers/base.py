"""Broker adapter interface.

Every broker (simulated or real) implements this small contract. Keeping it
tiny and explicit means the Hive-Mind, allocator and all risk governors don't
care whether they're driving a simulator or a real account.
"""


class BrokerError(Exception):
    """Raised when a broker call fails (auth, network, rejected order, etc.)."""


class BrokerAdapter:
    #: Human-readable name, e.g. "Simulator" or "Alpaca (paper)".
    name = "Abstract"
    #: True only when this adapter is connected to a LIVE (real-money) account.
    is_live = False
    #: True when the adapter is usable (connected / authenticated).
    connected = False

    # ------------------------------------------------------------------ #
    # Connection
    # ------------------------------------------------------------------ #
    def connect(self):
        """Establish/verify the connection. Returns a status dict."""
        raise NotImplementedError

    def disconnect(self):
        self.connected = False

    # ------------------------------------------------------------------ #
    # Account & data
    # ------------------------------------------------------------------ #
    def get_account(self):
        """Return {cash, equity, buying_power, currency}."""
        raise NotImplementedError

    def get_positions(self):
        """Return list of {symbol, qty, avg_price, side, market_value}."""
        raise NotImplementedError

    def get_price(self, symbol):
        """Return the latest price for ``symbol`` (or None)."""
        raise NotImplementedError

    # ------------------------------------------------------------------ #
    # Orders
    # ------------------------------------------------------------------ #
    def submit_order(self, symbol, qty, side, order_type="market",
                     time_in_force="day"):
        """Place an order. side in {'buy','sell'}. Returns an order dict."""
        raise NotImplementedError

    def close_position(self, symbol):
        """Flatten a single symbol. Returns an order dict (or None)."""
        raise NotImplementedError

    def close_all_positions(self):
        """Flatten everything. Returns count closed."""
        raise NotImplementedError
