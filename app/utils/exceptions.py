class ScraperException(Exception):
    """Base exception for scraper errors"""

    pass


class EmailException(Exception):
    """Base exception for email errors"""

    pass


class DatabaseException(Exception):
    """Base exception for database errors"""

    pass


class ConfigurationException(Exception):
    """Base exception for configuration errors"""

    pass
