import random
import undetected_chromedriver as uc
from fake_useragent import UserAgent
import json


class AntiDetectionService:
    def __init__(self):
        self.user_agent_rotator = UserAgent()

    def get_enhanced_chrome_options(self, proxy=None):
        """
        Create Chrome options with advanced anti-detection techniques

        Args:
            proxy (dict, optional): Proxy configuration

        Returns:
            Chrome options object
        """
        chrome_options = uc.ChromeOptions()

        # Randomize user agent
        user_agent = self.user_agent_rotator.random
        chrome_options.add_argument(f"user-agent={user_agent}")

        # WebDriver-specific anti-detection
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")

        # Proxy configuration
        if proxy:
            proxy_url = f"{proxy.protocol.value}://{proxy.ip}:{proxy.port}"
            chrome_options.add_argument(f"--proxy-server={proxy_url}")

        # Additional browser fingerprint randomization
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--disable-site-isolation-trials")
        chrome_options.add_argument("--disable-features=IsolateOrigins")
        chrome_options.add_argument("--disable-features=NetworkService")

        return chrome_options

    def create_wire_options(self, proxy=None):
        """
        Create Selenium Wire options for advanced proxy and request management

        Args:
            proxy (dict, optional): Proxy configuration

        Returns:
            Selenium Wire options
        """
        options = {"verify_ssl": False, "suppress_connection_errors": True}

        if proxy:
            options.update(
                {
                    "proxy": {
                        "http": f"{proxy['protocol']}://{proxy['ip']}:{proxy['port']}",
                        "https": f"{proxy['protocol']}://{proxy['ip']}:{proxy['port']}",
                        "no_proxy": "localhost,127.0.0.1",
                    }
                }
            )

        return options

    def enhance_webdriver_protection(self, driver):
        """
        Additional WebDriver protection techniques

        Args:
            driver: Selenium WebDriver instance
        """
        # Randomize WebDriver properties
        driver.execute_script(
            """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Randomize plugins
            Object.defineProperty(navigator, 'plugins', {
                get: function() {
                    const plugins = [
                        { name: 'Chrome PDF Plugin' },
                        { name: 'Chrome PDF Viewer' }
                    ];
                    return plugins;
                }
            });
        """
        )

        return driver
