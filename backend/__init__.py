"""
Assystent - Backend Package
"""

__version__ = "0.1.0"
__author__ = "Assistente Team"

# Import and expose core components for easy access
from .config.loader import ConfigLoader
from .core.interfaces import (
    BaseLLMClient,
    BaseSTTEngine,
    BaseTTSEngine,
    BaseVLMAnalyzer,
    GPUScheduler,
    CircuitBreaker,
    SessionWatchdog
)
from .db.migration_runner import MigrationRunner
from .db.repositories import (
    SessionRepository,
    MessageRepository,
    SystemStateRepository
)

# Initialize the package with basic configuration
import logging

# Set up basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

__all__ = [
    'ConfigLoader',
    'BaseLLMClient',
    'BaseSTTEngine', 
    'BaseTTSEngine',
    'BaseVLMAnalyzer',
    'GPUScheduler',
    'CircuitBreaker',
    'SessionWatchdog',
    'MigrationRunner',
    'SessionRepository',
    'MessageRepository',
    'SystemStateRepository'
]