"""
Performance Caching Module for Athletics Dashboard

Provides caching utilities for optimizing dashboard load times:
- SQLite query result caching
- Computed value caching (projections, benchmarks)
- Session-based caching for Streamlit
- Cache invalidation strategies

Target performance:
- Initial load: < 3 seconds
- Tab switch: < 500ms
- Data refresh: Background processing
"""

import sqlite3
import hashlib
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
import functools
import pickle

# Try to import streamlit for session state caching
try:
    import streamlit as st
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False

# Try to import pandas for DataFrame caching
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


class QueryCache:
    """
    Caches SQL query results to reduce database load.

    Uses a combination of:
    - In-memory cache for hot queries
    - File-based cache for persistence across sessions
    """

    def __init__(self, cache_dir: str = ".cache", max_memory_items: int = 100, ttl_seconds: int = 3600):
        """
        Initialize the query cache.

        Args:
            cache_dir: Directory for file-based cache
            max_memory_items: Maximum items in memory cache
            ttl_seconds: Time-to-live for cache entries
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

        self.memory_cache: Dict[str, Tuple[Any, float]] = {}
        self.max_memory_items = max_memory_items
        self.ttl_seconds = ttl_seconds

        self.hit_count = 0
        self.miss_count = 0

    def _hash_query(self, query: str, params: Optional[tuple] = None) -> str:
        """Generate a hash key for a query and parameters."""
        key_str = query + str(params or '')
        return hashlib.md5(key_str.encode()).hexdigest()

    def _is_expired(self, timestamp: float) -> bool:
        """Check if a cache entry has expired."""
        return time.time() - timestamp > self.ttl_seconds

    def get(self, query: str, params: Optional[tuple] = None) -> Optional[Any]:
        """
        Get a cached query result.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            Cached result or None if not found/expired
        """
        key = self._hash_query(query, params)

        # Check memory cache first
        if key in self.memory_cache:
            result, timestamp = self.memory_cache[key]
            if not self._is_expired(timestamp):
                self.hit_count += 1
                return result
            else:
                del self.memory_cache[key]

        # Check file cache
        cache_file = self.cache_dir / f"{key}.pkl"
        if cache_file.exists():
            try:
                with open(cache_file, 'rb') as f:
                    data = pickle.load(f)
                if not self._is_expired(data['timestamp']):
                    # Promote to memory cache
                    self._add_to_memory(key, data['result'], data['timestamp'])
                    self.hit_count += 1
                    return data['result']
                else:
                    cache_file.unlink()  # Delete expired
            except Exception:
                pass

        self.miss_count += 1
        return None

    def set(self, query: str, result: Any, params: Optional[tuple] = None):
        """
        Cache a query result.

        Args:
            query: SQL query string
            result: Query result to cache
            params: Query parameters
        """
        key = self._hash_query(query, params)
        timestamp = time.time()

        # Add to memory cache
        self._add_to_memory(key, result, timestamp)

        # Persist to file
        cache_file = self.cache_dir / f"{key}.pkl"
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump({'result': result, 'timestamp': timestamp}, f)
        except Exception:
            pass  # Fail silently on file cache errors

    def _add_to_memory(self, key: str, result: Any, timestamp: float):
        """Add item to memory cache, evicting if necessary."""
        if len(self.memory_cache) >= self.max_memory_items:
            # Evict oldest item
            oldest_key = min(self.memory_cache, key=lambda k: self.memory_cache[k][1])
            del self.memory_cache[oldest_key]

        self.memory_cache[key] = (result, timestamp)

    def invalidate(self, pattern: str = None):
        """
        Invalidate cache entries.

        Args:
            pattern: If None, clear all. Otherwise, clear matching entries.
        """
        if pattern is None:
            self.memory_cache.clear()
            for cache_file in self.cache_dir.glob("*.pkl"):
                cache_file.unlink()
        else:
            # Pattern-based invalidation not fully implemented
            # For now, just clear all
            self.invalidate()

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self.hit_count + self.miss_count
        hit_rate = (self.hit_count / total * 100) if total > 0 else 0

        return {
            'hits': self.hit_count,
            'misses': self.miss_count,
            'hit_rate': f"{hit_rate:.1f}%",
            'memory_items': len(self.memory_cache),
            'file_items': len(list(self.cache_dir.glob("*.pkl")))
        }


# Global query cache instance
_query_cache = QueryCache()


def cached_query(db_path: str, query: str, params: Optional[tuple] = None) -> pd.DataFrame:
    """
    Execute a query with caching.

    Args:
        db_path: Path to SQLite database
        query: SQL query string
        params: Query parameters

    Returns:
        Query results as DataFrame
    """
    if not PANDAS_AVAILABLE:
        raise ImportError("pandas required for cached_query")

    # Check cache
    cached = _query_cache.get(query, params)
    if cached is not None:
        return cached

    # Execute query
    conn = sqlite3.connect(db_path)
    try:
        if params:
            df = pd.read_sql_query(query, conn, params=params)
        else:
            df = pd.read_sql_query(query, conn)

        # Cache result
        _query_cache.set(query, df, params)
        return df
    finally:
        conn.close()


def streamlit_cache(ttl_seconds: int = 3600):
    """
    Decorator for Streamlit-compatible caching.

    Uses st.cache_data when available, falls back to simple memoization.

    Args:
        ttl_seconds: Cache time-to-live in seconds
    """
    def decorator(func: Callable):
        if STREAMLIT_AVAILABLE:
            # Use Streamlit's built-in caching
            return st.cache_data(ttl=ttl_seconds)(func)
        else:
            # Simple memoization fallback
            cache = {}

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                key = str(args) + str(sorted(kwargs.items()))
                if key in cache:
                    result, timestamp = cache[key]
                    if time.time() - timestamp < ttl_seconds:
                        return result
                result = func(*args, **kwargs)
                cache[key] = (result, time.time())
                return result

            return wrapper

    return decorator


class LazyLoader:
    """
    Lazy loader for deferred data loading.

    Loads data only when first accessed, with optional background pre-loading.
    """

    def __init__(self, loader_func: Callable, *args, **kwargs):
        """
        Initialize lazy loader.

        Args:
            loader_func: Function to call when data is needed
            *args, **kwargs: Arguments to pass to loader function
        """
        self.loader_func = loader_func
        self.args = args
        self.kwargs = kwargs
        self._data = None
        self._loaded = False
        self._loading = False
        self._error = None

    @property
    def data(self) -> Any:
        """Get the data, loading it if necessary."""
        if not self._loaded and not self._loading:
            self._load()
        return self._data

    def _load(self):
        """Load the data."""
        self._loading = True
        try:
            self._data = self.loader_func(*self.args, **self.kwargs)
            self._loaded = True
        except Exception as e:
            self._error = str(e)
        finally:
            self._loading = False

    @property
    def is_loaded(self) -> bool:
        """Check if data has been loaded."""
        return self._loaded

    @property
    def error(self) -> Optional[str]:
        """Get any loading error."""
        return self._error

    def invalidate(self):
        """Invalidate cached data."""
        self._data = None
        self._loaded = False
        self._error = None


class DataPreloader:
    """
    Pre-loads commonly accessed data in the background.

    Reduces initial load time by pre-loading data during idle periods.
    """

    def __init__(self):
        self.loaders: Dict[str, LazyLoader] = {}
        self.priorities: Dict[str, int] = {}

    def register(self, key: str, loader_func: Callable, priority: int = 5, *args, **kwargs):
        """
        Register a data loader.

        Args:
            key: Unique identifier for this data
            loader_func: Function to load the data
            priority: Loading priority (1=highest, 10=lowest)
            *args, **kwargs: Arguments for loader function
        """
        self.loaders[key] = LazyLoader(loader_func, *args, **kwargs)
        self.priorities[key] = priority

    def get(self, key: str) -> Any:
        """Get data by key."""
        if key not in self.loaders:
            raise KeyError(f"No loader registered for key: {key}")
        return self.loaders[key].data

    def preload_all(self):
        """Pre-load all registered data in priority order."""
        sorted_keys = sorted(self.priorities.keys(), key=lambda k: self.priorities[k])
        for key in sorted_keys:
            if not self.loaders[key].is_loaded:
                _ = self.loaders[key].data

    def invalidate(self, key: str = None):
        """Invalidate cached data."""
        if key:
            if key in self.loaders:
                self.loaders[key].invalidate()
        else:
            for loader in self.loaders.values():
                loader.invalidate()


# Optimized database loading functions
@streamlit_cache(ttl_seconds=1800)
def load_cached_sqlite(db_path: str, query: str = None) -> pd.DataFrame:
    """
    Load data from SQLite with caching.

    Args:
        db_path: Path to database
        query: Optional custom query (default: SELECT *)

    Returns:
        DataFrame with query results
    """
    if not PANDAS_AVAILABLE:
        raise ImportError("pandas required")

    conn = sqlite3.connect(db_path)
    try:
        if query:
            df = pd.read_sql_query(query, conn)
        else:
            # Get table name (assume single table db)
            tables = pd.read_sql_query(
                "SELECT name FROM sqlite_master WHERE type='table'", conn
            )
            if tables.empty:
                return pd.DataFrame()

            table_name = tables['name'].iloc[0]
            df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)

        return df
    finally:
        conn.close()


@streamlit_cache(ttl_seconds=3600)
def load_ksa_athletes_cached(db_path: str) -> pd.DataFrame:
    """Load KSA athletes with caching."""
    query = """
    SELECT *
    FROM results
    WHERE Athlete_CountryCode = 'KSA'
    ORDER BY Start_Date DESC
    """
    return load_cached_sqlite(db_path, query)


@streamlit_cache(ttl_seconds=3600)
def load_event_benchmarks_cached(db_path: str, event: str, gender: str) -> pd.DataFrame:
    """Load event benchmarks with caching."""
    query = f"""
    SELECT *
    FROM results
    WHERE Event = ?
      AND Gender = ?
      AND Competition_Name LIKE '%Championship%'
    ORDER BY Result_numeric
    """
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query(query, conn, params=(event, gender))
        return df
    finally:
        conn.close()


def optimize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Optimize DataFrame memory usage.

    Reduces memory footprint by:
    - Downcasting numeric types
    - Converting strings to categories where appropriate

    Args:
        df: DataFrame to optimize

    Returns:
        Optimized DataFrame
    """
    if not PANDAS_AVAILABLE:
        return df

    optimized = df.copy()

    for col in optimized.columns:
        col_type = optimized[col].dtype

        if col_type == 'object':
            # Convert strings with few unique values to category
            num_unique = optimized[col].nunique()
            num_total = len(optimized[col])
            if num_unique / num_total < 0.5:
                optimized[col] = optimized[col].astype('category')

        elif col_type == 'int64':
            # Downcast integers
            optimized[col] = pd.to_numeric(optimized[col], downcast='integer')

        elif col_type == 'float64':
            # Downcast floats
            optimized[col] = pd.to_numeric(optimized[col], downcast='float')

    return optimized


def get_cache_stats() -> Dict[str, Any]:
    """Get global cache statistics."""
    return _query_cache.stats()


def clear_all_caches():
    """Clear all caches."""
    _query_cache.invalidate()
    if STREAMLIT_AVAILABLE:
        st.cache_data.clear()


# Performance monitoring
class PerformanceMonitor:
    """Monitors and reports on dashboard performance."""

    def __init__(self):
        self.timings: Dict[str, List[float]] = {}

    def time_operation(self, operation_name: str):
        """Context manager for timing operations."""
        class Timer:
            def __init__(self, monitor, name):
                self.monitor = monitor
                self.name = name
                self.start_time = None

            def __enter__(self):
                self.start_time = time.time()
                return self

            def __exit__(self, *args):
                duration = (time.time() - self.start_time) * 1000  # ms
                if self.name not in self.monitor.timings:
                    self.monitor.timings[self.name] = []
                self.monitor.timings[self.name].append(duration)

        return Timer(self, operation_name)

    def get_stats(self) -> Dict[str, Dict[str, float]]:
        """Get timing statistics for all operations."""
        stats = {}
        for op, times in self.timings.items():
            if times:
                stats[op] = {
                    'avg_ms': sum(times) / len(times),
                    'min_ms': min(times),
                    'max_ms': max(times),
                    'count': len(times)
                }
        return stats

    def report(self) -> str:
        """Generate a performance report."""
        stats = self.get_stats()
        lines = ["Performance Report", "=" * 40]

        for op, metrics in sorted(stats.items()):
            lines.append(f"\n{op}:")
            lines.append(f"  Average: {metrics['avg_ms']:.1f}ms")
            lines.append(f"  Min: {metrics['min_ms']:.1f}ms")
            lines.append(f"  Max: {metrics['max_ms']:.1f}ms")
            lines.append(f"  Calls: {metrics['count']}")

        return "\n".join(lines)


# Global performance monitor
_perf_monitor = PerformanceMonitor()


def timed(func: Callable) -> Callable:
    """Decorator to time function execution."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with _perf_monitor.time_operation(func.__name__):
            return func(*args, **kwargs)
    return wrapper


def get_performance_report() -> str:
    """Get the global performance report."""
    return _perf_monitor.report()


# Module test
if __name__ == "__main__":
    print("Testing Performance Cache Module")
    print("=" * 40)

    # Test query cache
    cache = QueryCache(cache_dir=".test_cache", ttl_seconds=60)

    # Simulate caching
    test_query = "SELECT * FROM test WHERE id = ?"
    test_params = (1,)

    # First access - miss
    result = cache.get(test_query, test_params)
    print(f"First access (miss): {result}")

    # Cache some data
    cache.set(test_query, {"id": 1, "name": "test"}, test_params)

    # Second access - hit
    result = cache.get(test_query, test_params)
    print(f"Second access (hit): {result}")

    # Stats
    print(f"\nCache stats: {cache.stats()}")

    # Clean up
    cache.invalidate()

    print("\nPerformance cache tests complete!")
