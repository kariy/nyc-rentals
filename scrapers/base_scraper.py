import time
import random
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


class BaseScraper:
    def __init__(self, headless=True):
        # Setup Chrome options
        chrome_options = Options()

        if headless:
            chrome_options.add_argument("--headless")

        # Add realistic user agent
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)

        # Initialize webdriver
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()), options=chrome_options
        )

        self.driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        # Set current neighborhood and property type for context
        self.current_neighborhood = None
        self.current_property_type = None
        self.current_source = None

    def scroll_page(self, scroll_pauses=5, scroll_increment=800):
        """Scroll down the page to load all properties"""
        last_height = self.driver.execute_script("return document.body.scrollHeight")

        for i in range(scroll_pauses):
            self.driver.execute_script(f"window.scrollBy(0, {scroll_increment});")
            time.sleep(random.uniform(1, 2))

            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                self.driver.execute_script(
                    "window.scrollTo(0, document.body.scrollHeight);"
                )
                time.sleep(random.uniform(1, 2))
                break
            last_height = new_height
            time.sleep(random.uniform(0.5, 1.5))

    def try_selectors(self, element, selectors):
        """Try multiple selectors and return the first match's text"""
        for selector in selectors:
            try:
                found_element = element.select_one(selector)
                if found_element:
                    return found_element.text.strip()
            except:
                continue
        return None

    def close(self):
        """Close the webdriver"""
        self.driver.quit()
