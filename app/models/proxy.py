from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, Enum
from datetime import datetime
import enum
from ..db.base import Base


class ProxyProtocol(enum.Enum):
    HTTP = "http"
    HTTPS = "https"
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"


class AnonymityLevel(enum.Enum):
    TRANSPARENT = "transparent"
    ANONYMOUS = "anonymous"
    HIGH_ANONYMITY = "high_anonymity"


class Proxy(Base):
    __tablename__ = "proxies"

    id = Column(Integer, primary_key=True, index=True)

    # Core Proxy Information
    ip = Column(String, unique=True, index=True)
    port = Column(Integer)
    protocol = Column(Enum(ProxyProtocol), nullable=False)

    # Geolocation Details
    country = Column(String)
    city = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    # Anonymity and Performance
    anonymity = Column(Enum(AnonymityLevel), nullable=False)
    is_active = Column(Boolean, default=True)

    # Performance Metrics
    success_rate = Column(Float, default=0.0)
    avg_response_time = Column(Float, default=0.0)
    consecutive_failures = Column(Integer, default=0)

    # Detailed Performance Tracking
    total_requests = Column(Integer, default=0)
    successful_requests = Column(Integer, default=0)
    failed_requests = Column(Integer, default=0)

    # Timestamp Tracking
    last_checked = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Additional Flags
    supports_ssl = Column(Boolean, default=False)
    supports_streaming = Column(Boolean, default=False)

    # Provider and Source Information
    provider = Column(String, nullable=True)
    source_type = Column(String, nullable=True)

    # Scoring Mechanism
    reliability_score = Column(Float, default=0.0)
    performance_score = Column(Float, default=0.0)

    def update_performance_metrics(self, is_successful: bool, response_time: float):
        """
        Update proxy performance metrics

        Args:
            is_successful (bool): Whether the request was successful
            response_time (float): Response time of the request
        """
        self.total_requests += 1

        if is_successful:
            self.successful_requests += 1
            self.avg_response_time = (
                self.avg_response_time * (self.successful_requests - 1) + response_time
            ) / self.successful_requests
            self.consecutive_failures = 0
        else:
            self.failed_requests += 1
            self.consecutive_failures += 1

        # Recalculate success rate
        self.success_rate = (self.successful_requests / self.total_requests) * 100

        # Update reliability and performance scores
        self._calculate_scores()

    def _calculate_scores(self):
        """
        Calculate reliability and performance scores
        """
        # Reliability score (based on success rate and consecutive failures)
        reliability_components = [
            self.success_rate / 100,  # Success rate (0-1)
            1 / (1 + self.consecutive_failures),  # Penalty for consecutive failures
        ]
        self.reliability_score = (
            sum(reliability_components) / len(reliability_components) * 10
        )

        # Performance score (based on response time and reliability)
        max_acceptable_response_time = 1.0  # 1 second
        response_time_score = max(
            0, 1 - (self.avg_response_time / max_acceptable_response_time)
        )

        performance_components = [
            response_time_score,
            self.reliability_score / 10,  # Normalize reliability score
        ]
        self.performance_score = (
            sum(performance_components) / len(performance_components) * 10
        )

    def mark_inactive(self):
        """
        Mark proxy as inactive if it fails too many times
        """
        if self.consecutive_failures > 5:
            self.is_active = False

    @classmethod
    def create_proxy(
        cls,
        ip: str,
        port: int,
        protocol: ProxyProtocol,
        country: str,
        anonymity: AnonymityLevel,
        **kwargs
    ):
        """
        Class method to create a new proxy instance

        Args:
            ip (str): Proxy IP address
            port (int): Proxy port
            protocol (ProxyProtocol): Proxy protocol
            country (str): Country of the proxy
            anonymity (AnonymityLevel): Anonymity level
            **kwargs: Additional proxy attributes

        Returns:
            Proxy instance
        """
        return cls(
            ip=ip,
            port=port,
            protocol=protocol,
            country=country,
            anonymity=anonymity,
            **kwargs
        )

    def to_dict(self):
        """
        Convert proxy to dictionary representation

        Returns:
            Dict of proxy attributes
        """
        return {
            "id": self.id,
            "ip": self.ip,
            "port": self.port,
            "protocol": self.protocol.value,
            "country": self.country,
            "anonymity": self.anonymity.value,
            "is_active": self.is_active,
            "success_rate": self.success_rate,
            "avg_response_time": self.avg_response_time,
            "reliability_score": self.reliability_score,
            "performance_score": self.performance_score,
        }
