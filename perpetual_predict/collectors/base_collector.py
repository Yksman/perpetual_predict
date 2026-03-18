"""Base collector abstract class."""

from abc import ABC, abstractmethod
from typing import Any


class BaseCollector(ABC):
    """Abstract base class for data collectors.

    All collectors should inherit from this class and implement
    the collect() method.
    """

    @abstractmethod
    async def collect(self, **kwargs: Any) -> Any:
        """Collect data from the source.

        Args:
            **kwargs: Collector-specific arguments.

        Returns:
            Collected data in the appropriate format.
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close any open connections or resources."""
        pass
