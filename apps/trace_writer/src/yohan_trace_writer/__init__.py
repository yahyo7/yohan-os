"""yohan_trace_writer — persist every bus event to the traces table.

This process is the concrete payoff of using Redis Streams over pub/sub: it joins
the results stream as its OWN consumer group (``grp:tracewriter``), completely
independent of the gateway's relay group. Both see every event; neither disturbs
the other. Adding this observer required zero changes to the gateway or agents —
exactly the "add capability without rewriting the core" property the whole
architecture is built for.
"""
