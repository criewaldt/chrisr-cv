"""Job source adapters. Importing this package registers every adapter."""
from .base import (JobSourceAdapter, RawPosting, fetch_all, get_adapter,  # noqa: F401
                   register, registered_kinds)

from . import (arbeitnow, ashby, greenhouse, hn_hiring, lever,  # noqa: F401,E402
               remoteok, remotive)

__all__ = ['JobSourceAdapter', 'RawPosting', 'fetch_all', 'get_adapter',
           'register', 'registered_kinds']
