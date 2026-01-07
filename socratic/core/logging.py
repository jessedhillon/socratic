import logging
import typing as t


class TraceLogLevelLogger(logging.Logger):
    def trace(self, message: str, *args: t.Any, **kwargs: t.Any):
        loglevel = getattr(logging, "TRACE", 5)
        if self.isEnabledFor(loglevel):
            self._log(loglevel, message, args, **kwargs)
