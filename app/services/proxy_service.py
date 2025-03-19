from loguru import logger
from typing import List, Dict, Optional
import requests
from sqlalchemy.orm import Session, load_only
from sqlalchemy import and_, or_
import random
import concurrent.futures
import time
from datetime import datetime, timedelta

from ..utils.proxy_validator import ProxyValidator
from ..models.proxy import Proxy, ProxyProtocol, AnonymityLevel


class ProxyService:
    def __init__(self, db: Session):
        self.db = db
        self.validator = ProxyValidator()
        self.min_reliable_score = 7.0  # Minimum performance score for consideration

    def get_validated_proxies(self, min_success_rate: float = 50.0) -> List[Proxy]:
        """Get active proxies with advanced filters"""
        try:
            hour_ago = datetime.utcnow() - timedelta(hours=1)
            return (
                self.db.query(Proxy)
                .filter(
                    and_(
                        Proxy.is_active == True,
                        Proxy.success_rate >= min_success_rate,
                        Proxy.performance_score >= self.min_reliable_score,
                        Proxy.last_checked >= hour_ago,
                    )
                )
                .options(
                    load_only(
                        Proxy.ip, Proxy.port, Proxy.protocol, Proxy.performance_score
                    )
                )
                .order_by(Proxy.performance_score.desc())
                .limit(100)  # Increased pool for better selection
                .all()
            )
        except Exception as e:
            logger.error(f"Proxy query failed: {e}")
            return []

    def get_random_proxy(self) -> Optional[Proxy]:
        """Improved weighted selection with freshness check"""
        proxies = self.get_validated_proxies()
        if not proxies:
            return None

        # Exponential weighting for better distribution
        max_score = max(p.performance_score for p in proxies)
        weights = [(p.performance_score / max_score) ** 2 for p in proxies]

        selected = random.choices(proxies, weights=weights, k=1)[0]
        logger.info(
            f"Selected proxy {selected.ip}:{selected.port} with score {selected.performance_score}"
        )
        return selected

    def update_proxy_stats(self, proxy: Proxy, success: bool, response_time: float):
        """Atomic update with performance safeguards"""
        try:
            proxy.total_requests += 1

            if success:
                proxy.successful_requests += 1
                proxy.consecutive_failures = 0
                # Weighted average for response time
                proxy.avg_response_time = 0.8 * proxy.avg_response_time + 0.2 * min(
                    response_time, 10.0
                )  # Cap outlier values
            else:
                proxy.failed_requests += 1
                proxy.consecutive_failures += 1

            # Update derived metrics
            proxy.success_rate = (
                (proxy.successful_requests / proxy.total_requests) * 100
                if proxy.total_requests > 0
                else 0
            )
            proxy.is_active = (
                proxy.consecutive_failures < 5
                and proxy.success_rate >= 30
                and proxy.avg_response_time <= 8.0
            )
            proxy.last_checked = datetime.utcnow()

            self._calculate_performance_score(proxy)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Proxy update failed: {e}")

    def refresh_proxies(self):
        """Enhanced refresh pipeline with failure handling"""
        try:
            # Soft delete instead of hard delete
            self.db.query(Proxy).filter(Proxy.consecutive_failures >= 5).update(
                {"is_active": False}
            )

            # Fetch from multiple sources with fallback
            raw_proxies = self._fetch_proxy_sources()
            if not raw_proxies:
                raw_proxies = self._fallback_sources()

            # Parallel validation with progress tracking
            validated = self.validator.bulk_validate(
                raw_proxies, timeout=15, concurrency=30
            )

            # Batch upsert for better performance
            self._bulk_upsert(validated)

            self.db.commit()
            logger.success(f"Refreshed {len(validated)} proxies")
            return len(validated)
        except Exception as e:
            self.db.rollback()
            logger.critical(f"Proxy refresh failed: {e}")
            return 0

    def _bulk_upsert(self, proxies: List[Dict]):
        """Batch upsert operation"""
        existing_proxies = {
            (p.ip, p.port): p
            for p in self.db.query(Proxy)
            .filter(
                or_(
                    *[
                        (Proxy.ip == p["ip"]) & (Proxy.port == p["port"])
                        for p in proxies
                    ]
                )
            )
            .all()
        }

        for p_data in proxies:
            key = (p_data["ip"], p_data["port"])
            if key in existing_proxies:
                proxy = existing_proxies[key]
                proxy.protocol = p_data.get("protocol", proxy.protocol)
                proxy.country = p_data.get("country", proxy.country)
                proxy.anonymity = p_data.get("anonymity", proxy.anonymity)
                proxy.is_active = True
            else:
                self.db.add(
                    Proxy(
                        ip=p_data["ip"],
                        port=p_data["port"],
                        protocol=p_data.get("protocol", ProxyProtocol.HTTP),
                        country=p_data.get("country", "Unknown"),
                        anonymity=p_data.get("anonymity", AnonymityLevel.TRANSPARENT),
                        is_active=True,
                        last_checked=datetime.utcnow(),
                    )
                )

    def _fetch_proxy_sources(self) -> List[Dict]:
        """Fetch from multiple sources with improved error handling"""
        sources = [
            # ("https://proxylist.geonode.com/api/proxy-list", self._parse_geonode),
            # (
            #     "https://api.proxyscrape.com/v2/?request=getproxies",
            #     self._parse_proxyscrape,
            # ),
            (
                "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
                self._parse_plaintext,
            ),
        ]

        proxies = []
        for url, parser in sources:
            try:
                response = requests.get(
                    url,
                    timeout=15,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    },
                )
                response.raise_for_status()
                proxies.extend(parser(response))
            except Exception as e:
                logger.warning(f"Failed to fetch from {url}: {e}")
        return proxies

    def _parse_plaintext(self, response) -> List[Dict]:
        """Parse plaintext IP:port lists"""
        return [
            {
                "ip": line.split(":")[0].strip(),
                "port": int(line.split(":")[1].strip()),
                "protocol": ProxyProtocol.HTTP.value,
                "country": "Unknown",
                "anonymity": AnonymityLevel.UNKNOWN.value,
            }
            for line in response.text.split("\n")
            if ":" in line
        ]

    def _calculate_performance_score(self, proxy: Proxy):
        """Advanced performance scoring"""
        response_score = max(0, 1 - (proxy.avg_response_time / 10))  # 0-1
        success_score = proxy.success_rate / 100  # 0-1
        freshness_score = (
            1
            if (datetime.utcnow() - proxy.last_checked).total_seconds() < 3600
            else 0.5
        )

        proxy.performance_score = round(
            (response_score * 0.4 + success_score * 0.5 + freshness_score * 0.1) * 10, 2
        )

    def _fallback_sources(self) -> List[Dict]:
        """Emergency fallback sources"""
        logger.warning("Using fallback proxy sources")
        return [
            {
                "ip": "104.234.110.142",
                "port": 8080,
                "protocol": "http",
                "country": "US",
                "anonymity": "anonymous",
            },
            {
                "ip": "192.111.139.165",
                "port": 4145,
                "protocol": "socks4",
                "country": "US",
                "anonymity": "anonymous",
            },
        ]
