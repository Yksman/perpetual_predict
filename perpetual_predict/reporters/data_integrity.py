"""Data integrity verification for collected market data."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from perpetual_predict.storage.database import Database
from perpetual_predict.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DataIntegrityResult:
    """Result of integrity check for a single data type."""

    data_type: str
    interval_hours: int
    expected_count: int
    actual_count: int
    gaps: list[datetime] = field(default_factory=list)
    duplicates: list[datetime] = field(default_factory=list)

    @property
    def has_gaps(self) -> bool:
        """Check if there are any gaps in the data."""
        return len(self.gaps) > 0

    @property
    def has_duplicates(self) -> bool:
        """Check if there are any duplicate records."""
        return len(self.duplicates) > 0

    @property
    def is_healthy(self) -> bool:
        """Check if the data is healthy (no gaps, no duplicates)."""
        return not self.has_gaps and not self.has_duplicates

    def format_status(self) -> str:
        """Format status for display."""
        if self.is_healthy:
            return f"✅ {self.actual_count}/{self.expected_count} 레코드"
        elif self.has_gaps:
            gap_times = ", ".join(
                g.strftime("%m-%d %H:%M") for g in self.gaps[:3]
            )
            suffix = f" 외 {len(self.gaps) - 3}개" if len(self.gaps) > 3 else ""
            return f"⚠️ {self.actual_count}/{self.expected_count} | 갭: {gap_times}{suffix}"
        else:
            return f"⚠️ {self.actual_count}/{self.expected_count} | 중복 발견"


@dataclass
class FearGreedIntegrityResult:
    """Special result for Fear & Greed Index (daily data)."""

    data_type: str = "fear_greed"
    has_today: bool = False
    latest_date: datetime | None = None

    @property
    def is_healthy(self) -> bool:
        """Check if today's data exists."""
        return self.has_today

    def format_status(self) -> str:
        """Format status for display."""
        if self.has_today:
            return "✅ 오늘 데이터 존재"
        elif self.latest_date:
            return f"⚠️ 최신: {self.latest_date.strftime('%Y-%m-%d')}"
        else:
            return "❌ 데이터 없음"


@dataclass
class IntegrityReport:
    """Complete integrity report for all data types."""

    candles: DataIntegrityResult
    funding_rates: DataIntegrityResult
    open_interest: DataIntegrityResult
    long_short_ratio: DataIntegrityResult
    fear_greed: FearGreedIntegrityResult
    verification_time: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    hours_checked: int = 24

    @property
    def overall_healthy(self) -> bool:
        """Check if all data types are healthy."""
        return all([
            self.candles.is_healthy,
            self.funding_rates.is_healthy,
            self.open_interest.is_healthy,
            self.long_short_ratio.is_healthy,
            self.fear_greed.is_healthy,
        ])

    @property
    def has_warnings(self) -> bool:
        """Check if any data type has warnings."""
        return not self.overall_healthy


def _generate_expected_timestamps(
    end_time: datetime,
    hours: int,
    interval_hours: int,
) -> list[datetime]:
    """Generate list of expected timestamps for a given interval.

    Args:
        end_time: End time (usually now, aligned to interval).
        hours: Number of hours to look back.
        interval_hours: Interval between expected timestamps.

    Returns:
        List of expected timestamps, oldest first.
    """
    # Align end_time to the nearest interval boundary
    aligned_hour = (end_time.hour // interval_hours) * interval_hours
    aligned_end = end_time.replace(
        hour=aligned_hour, minute=0, second=0, microsecond=0
    )

    expected = []
    current = aligned_end
    start_time = aligned_end - timedelta(hours=hours)

    while current > start_time:
        expected.append(current)
        current -= timedelta(hours=interval_hours)

    return sorted(expected)


def _find_gaps(
    expected: list[datetime],
    actual: list[datetime],
    tolerance_minutes: int = 30,
) -> list[datetime]:
    """Find gaps between expected and actual timestamps.

    Args:
        expected: List of expected timestamps.
        actual: List of actual timestamps from DB.
        tolerance_minutes: Tolerance for matching timestamps.

    Returns:
        List of missing timestamps.
    """
    tolerance = timedelta(minutes=tolerance_minutes)
    actual_set = set(actual)

    gaps = []
    for exp in expected:
        # Check if any actual timestamp is within tolerance
        found = any(
            abs((act - exp).total_seconds()) < tolerance.total_seconds()
            for act in actual_set
        )
        if not found:
            gaps.append(exp)

    return gaps


def _find_duplicates(timestamps: list[datetime]) -> list[datetime]:
    """Find duplicate timestamps.

    Args:
        timestamps: List of timestamps.

    Returns:
        List of duplicate timestamps.
    """
    seen = set()
    duplicates = []
    for ts in timestamps:
        # Normalize to hour precision for comparison
        normalized = ts.replace(minute=0, second=0, microsecond=0)
        if normalized in seen:
            duplicates.append(ts)
        seen.add(normalized)
    return duplicates


async def _verify_candles(
    db: Database,
    symbol: str,
    timeframe: str,
    hours: int,
) -> DataIntegrityResult:
    """Verify candle data integrity."""
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(hours=hours)

    candles = await db.get_candles(
        symbol=symbol,
        timeframe=timeframe,
        start_time=start_time,
    )

    interval_hours = 4  # 4H candles
    expected = _generate_expected_timestamps(now, hours, interval_hours)
    actual = [c.open_time for c in candles]

    gaps = _find_gaps(expected, actual)
    duplicates = _find_duplicates(actual)

    return DataIntegrityResult(
        data_type="candles",
        interval_hours=interval_hours,
        expected_count=len(expected),
        actual_count=len(candles),
        gaps=gaps,
        duplicates=duplicates,
    )


async def _verify_funding_rates(
    db: Database,
    symbol: str,
    hours: int,
) -> DataIntegrityResult:
    """Verify funding rate data integrity."""
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(hours=hours)

    rates = await db.get_funding_rates(
        symbol=symbol,
        start_time=start_time,
    )

    interval_hours = 8  # Funding rates are every 8 hours
    expected = _generate_expected_timestamps(now, hours, interval_hours)
    actual = [r.funding_time for r in rates]

    gaps = _find_gaps(expected, actual)
    duplicates = _find_duplicates(actual)

    return DataIntegrityResult(
        data_type="funding_rates",
        interval_hours=interval_hours,
        expected_count=len(expected),
        actual_count=len(rates),
        gaps=gaps,
        duplicates=duplicates,
    )


async def _verify_open_interest(
    db: Database,
    symbol: str,
    hours: int,
) -> DataIntegrityResult:
    """Verify open interest data integrity."""
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(hours=hours)

    ois = await db.get_open_interests(
        symbol=symbol,
        start_time=start_time,
    )

    interval_hours = 4  # 4H intervals
    expected = _generate_expected_timestamps(now, hours, interval_hours)
    actual = [o.timestamp for o in ois]

    gaps = _find_gaps(expected, actual)
    duplicates = _find_duplicates(actual)

    return DataIntegrityResult(
        data_type="open_interest",
        interval_hours=interval_hours,
        expected_count=len(expected),
        actual_count=len(ois),
        gaps=gaps,
        duplicates=duplicates,
    )


async def _verify_long_short_ratio(
    db: Database,
    symbol: str,
    hours: int,
) -> DataIntegrityResult:
    """Verify long/short ratio data integrity."""
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(hours=hours)

    ratios = await db.get_long_short_ratios(
        symbol=symbol,
        start_time=start_time,
    )

    interval_hours = 4  # 4H intervals
    expected = _generate_expected_timestamps(now, hours, interval_hours)
    actual = [r.timestamp for r in ratios]

    gaps = _find_gaps(expected, actual)
    duplicates = _find_duplicates(actual)

    return DataIntegrityResult(
        data_type="long_short_ratio",
        interval_hours=interval_hours,
        expected_count=len(expected),
        actual_count=len(ratios),
        gaps=gaps,
        duplicates=duplicates,
    )


async def _verify_fear_greed(db: Database) -> FearGreedIntegrityResult:
    """Verify Fear & Greed Index data integrity."""
    today = datetime.now(timezone.utc).date()

    fgs = await db.get_fear_greeds(limit=1)

    if not fgs:
        return FearGreedIntegrityResult(has_today=False, latest_date=None)

    latest = fgs[0]
    latest_date = latest.timestamp.date() if latest.timestamp else None
    has_today = latest_date == today if latest_date else False

    return FearGreedIntegrityResult(
        has_today=has_today,
        latest_date=latest.timestamp if latest_date else None,
    )


async def verify_data_integrity(
    db: Database,
    symbol: str = "BTCUSDT",
    timeframe: str = "4h",
    hours: int = 24,
) -> IntegrityReport:
    """Verify data integrity for all data types.

    Args:
        db: Database connection.
        symbol: Trading symbol.
        timeframe: Candle timeframe.
        hours: Number of hours to check (default: 24).

    Returns:
        IntegrityReport with verification results.
    """
    logger.info(f"Verifying data integrity for {symbol} (last {hours} hours)")

    candles = await _verify_candles(db, symbol, timeframe, hours)
    funding_rates = await _verify_funding_rates(db, symbol, hours)
    open_interest = await _verify_open_interest(db, symbol, hours)
    long_short_ratio = await _verify_long_short_ratio(db, symbol, hours)
    fear_greed = await _verify_fear_greed(db)

    report = IntegrityReport(
        candles=candles,
        funding_rates=funding_rates,
        open_interest=open_interest,
        long_short_ratio=long_short_ratio,
        fear_greed=fear_greed,
        hours_checked=hours,
    )

    if report.overall_healthy:
        logger.info("Data integrity check passed: all data healthy")
    else:
        logger.warning("Data integrity check found issues")

    return report
