"""yohan_gateway — the single entry point for every command.

Regardless of channel (Telegram now; the dashboard later), a command enters here,
becomes a ``command_received`` event, and is published to the bus. The gateway
also relays results back out: it consumes the results stream and sends replies to
the originating channel. It never runs agent logic itself.
"""
