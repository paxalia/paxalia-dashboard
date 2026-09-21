from django.apps import AppConfig
from django.core.signals import request_started


class AnalyticsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'paxalia'

    def ready(self):
        from . import signals
        signals.register_signals()

        # Configure the canonical logging handler after the app registry is
        # ready. A request-start hook also re-checks the logger boundaries so
        # ASGI/Daphne or a host logging configuration that mutates handlers
        # after Django startup cannot silently disable Paxalia Logs.
        try:
            from .logging.handler import configure_logging

            configure_logging()

            def _ensure_paxalia_logging(sender, **kwargs):
                configure_logging()

            request_started.connect(
                _ensure_paxalia_logging,
                dispatch_uid='paxalia.ensure_logging_request_started',
                weak=False,
            )
        except Exception:
            # Logging must never prevent Django from starting.
            pass
