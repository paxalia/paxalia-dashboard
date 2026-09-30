"""Compatibility-friendly entry point for scheduled Paxalia Availability checks."""
from .check_uptime import Command as UptimeCommand


class Command(UptimeCommand):
    help = 'Run due Paxalia Availability monitor checks using the existing uptime engine.'
