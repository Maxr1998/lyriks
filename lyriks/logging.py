from httpx import RequestError
from stamina.instrumentation import RetryDetails, RetryHook, RetryHookFactory

DEFAULT_LOG_LEVEL = 30


def init_logging() -> RetryHook:
    """
    Initialize a retry hook that will log a message depending
    on the exception type that caused the retry.
    """

    import logging

    logger = logging.getLogger("retry")

    def log_retries(details: RetryDetails) -> None:
        if isinstance(details.caused_by, RequestError):
            # Log message on httpx request failures
            logger.log(
                DEFAULT_LOG_LEVEL,
                f"Network request failed in {details.name}, retrying in {round(details.wait_for, 2)}s…",
                extra={
                    "function": details.name,
                    "retry_num": details.retry_num,
                    "caused_by": repr(details.caused_by),
                    "wait_for": round(details.wait_for, 2),
                    "waited_so_far": round(details.waited_so_far, 2),
                },
            )

    return log_retries


LoggingOnRetryHook = RetryHookFactory(init_logging)
