"""app/publishers. Pluggable destination publishers (Instagram, etc.).

Each module in this package is a self-contained publisher that can be
opted into via the Settings page. They follow the same Protocol as the
publishers in :mod:`app.publisher` and register themselves with the
shared registry at startup when their credentials are present.
"""
