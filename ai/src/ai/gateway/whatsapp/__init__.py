"""WhatsApp gateway — requires the optional ``neonize`` extra.

Import guard: importing this package does NOT load neonize.  Only
``WhatsAppClient.start()`` triggers the neonize import so the main
harness process never needs the extra installed.
"""
