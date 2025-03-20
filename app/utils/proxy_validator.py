import ipaddress
import socket
import time
import concurrent
import requests
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import random


class ProxyValidator:
    def __init__(self):
        self.test_urls = [
            ("https://www.google.com", 2),  # More reliable test URL
            ("https://api.myip.com", 2),
        ]
        self.min_success_rate = 75
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
        ]

    def bulk_validate(
        self, proxies: List[Dict], timeout: int = 8, concurrency: int = 20
    ) -> List[Dict]:
        """Comprehensive proxy validation with multiple checks"""
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = {
                executor.submit(self.full_validation, p, timeout): p for p in proxies
            }

            results = []
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    if result and result["is_valid"]:
                        results.append(result)
                except Exception as e:
                    continue
            return results

    def full_validation(self, proxy: Dict, timeout: int) -> Optional[Dict]:
        """Complete proxy validation pipeline"""
        try:
            # Initial checks
            if not self._validate_ip_port(proxy["ip"], proxy["port"]):
                return None

            # Protocol verification
            protocol = self._detect_protocol(proxy, timeout)
            if not protocol:
                return None

            # Update protocol information
            proxy["protocol"] = protocol

            # Performance metrics
            success_count = 0
            total_tests = 0
            response_times = []

            # Multi-test validation
            for url, attempts in self.test_urls:
                for _ in range(attempts):
                    test_result, response_time = self._test_proxy(proxy, url, timeout)
                    if test_result:
                        success_count += 1
                        response_times.append(response_time)
                    total_tests += 1

            # Calculate metrics
            success_rate = (success_count / total_tests) * 100 if total_tests > 0 else 0
            avg_response = (
                sum(response_times) / len(response_times) if response_times else 999
            )

            # Final validation
            if success_rate < self.min_success_rate:
                return None

            return {
                **proxy,
                "is_valid": True,
                "success_rate": round(success_rate, 1),
                "avg_response_time": round(avg_response, 2),
                "anonymity": self._check_anonymity(proxy, timeout),
                "supports_https": self._test_https_support(proxy, timeout),
                "last_checked": time.time(),
            }
        except Exception as e:
            return None

    def _create_session(self, retries=3):
        """Create resilient HTTP session"""
        session = requests.Session()
        retry = Retry(
            total=retries, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _validate_ip_port(self, ip: str, port: int) -> bool:
        """Comprehensive IP/Port validation"""
        try:
            if not (1 <= port <= 65535):
                return False
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False

    def _detect_protocol(self, proxy: Dict, timeout: int) -> Optional[str]:
        """Auto-detect supported protocols"""
        for protocol in ["https", "socks5", "http"]:
            try:
                if self._test_protocol(proxy, protocol, timeout):
                    return protocol
            except:
                continue
        return None

    def _test_protocol(
        self, proxy: Dict, protocol: str, timeout: int
    ) -> Tuple[bool, float]:
        """Test protocol with verification"""
        # proxies = {
        #     "http": f"{protocol}://{proxy['ip']}:{proxy['port']}",
        #     "https": f"{protocol}://{proxy['ip']}:{proxy['port']}",
        # }

        try:
            if protocol.lower() == "socks5":
                proxy_str = f'socks5://{proxy["ip"]}:{proxy["port"]}'
            else:
                proxy_str = f'{protocol}://{proxy["ip"]}:{proxy["port"]}'

            proxies = {"http": proxy_str, "https": proxy_str}
            start = time.time()
            with self._create_session() as session:
                response = session.get(
                    "http://httpbin.org/ip",
                    proxies=proxies,
                    timeout=timeout,
                    headers={"User-Agent": random.choice(self.user_agents)},
                )
                if response.ok and proxy["ip"] in response.text:
                    return True, time.time() - start
            return False, 999
        except:
            return False, 999

    def _test_https_support(self, proxy: Dict, timeout: int) -> bool:
        """Verify HTTPS support"""
        try:
            with self._create_session() as session:
                response = session.get(
                    "https://httpbin.org/ip",
                    proxies={
                        "https": f"{proxy['protocol']}://{proxy['ip']}:{proxy['port']}"
                    },
                    timeout=timeout,
                    verify=False,  # Allow self-signed certificates
                )
                return response.ok and proxy["ip"] in response.text
        except:
            return False

    def _check_anonymity(self, proxy: Dict, timeout: int) -> str:
        """Advanced anonymity detection"""
        try:
            with self._create_session() as session:
                # Test 1: Standard headers check
                response = session.get(
                    "http://httpbin.org/headers",
                    proxies={
                        proxy[
                            "protocol"
                        ]: f"{proxy['protocol']}://{proxy['ip']}:{proxy['port']}"
                    },
                    timeout=timeout,
                )
                headers = response.json().get("headers", {})

                # Test 2: DNS leak test
                dns_response = session.get(
                    "https://dnsleaktest.com",
                    timeout=timeout,
                    proxies={
                        proxy[
                            "protocol"
                        ]: f"{proxy['protocol']}://{proxy['ip']}:{proxy['port']}"
                    },
                )

                # Anonymity detection
                anonymity_level = "high_anonymity"
                if any(h in headers for h in ["Via", "X-Forwarded-For", "Forwarded"]):
                    anonymity_level = "anonymous"
                if "Proxy-Connection" in headers or "X-Proxy-ID" in headers:
                    anonymity_level = "transparent"

                # DNS leak detection
                if proxy["ip"] not in dns_response.text:
                    anonymity_level = "transparent"

                return anonymity_level
        except:
            return "transparent"
