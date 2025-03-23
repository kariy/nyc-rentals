import time
import random
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from scrapers.base_scraper import BaseScraper


class ApartmentsScraper(BaseScraper):
    def __init__(self, headless=True):
        super().__init__(headless)
        self.current_source = "apartments.com"

    def scrape_neighborhood(self, neighborhood_name, property_type="rent", max_pages=3):
        """Scrape Apartments.com listings for a specific neighborhood"""
        print(f"Scraping Apartments.com - {neighborhood_name}...")
        self.current_neighborhood = neighborhood_name
        self.current_property_type = property_type

        # Apartments.com has different URL structure
        neighborhood_formatted = neighborhood_name.replace("-", "-").lower()

        # Apartments.com only has rentals
        search_url = f"https://www.apartments.com/new-york/{neighborhood_formatted}/"

        self.driver.get(search_url)
        time.sleep(random.uniform(3, 5))

        # Wait for page to load
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div.placardContainer")
                )
            )
        except:
            print(f"Timeout or error loading {search_url}")
            return []

        self.scroll_page(scroll_pauses=8)  # More scrolling for apartments.com

        # Extract properties (pagination works differently on apartments.com)
        soup = BeautifulSoup(self.driver.page_source, "html.parser")
        properties = self.extract_properties(soup)

        print(f"Apartments.com: Extracted {len(properties)} properties")

        return properties

    def extract_properties(self, soup):
        """Extract property data from Apartments.com's HTML"""
        property_cards = soup.select("article.placard")

        properties = []
        for card in property_cards:
            try:
                # Price
                price_elem = card.select_one("div.price-range")
                price = price_elem.text.strip() if price_elem else "N/A"

                # Address
                address_elem = card.select_one("div.property-address")
                address = address_elem.text.strip() if address_elem else "N/A"

                # Beds
                beds_elem = card.select_one("div.bed-range")
                beds = beds_elem.text.strip() if beds_elem else "N/A"

                # Baths
                baths_elem = card.select_one("div.bath-range")
                baths = baths_elem.text.strip() if baths_elem else "N/A"

                # Square footage
                sqft_elem = card.select_one("div.sqft-range")
                sqft = sqft_elem.text.strip() if sqft_elem else "N/A"

                properties.append(
                    {
                        "source": "apartments.com",
                        "neighborhood": self.current_neighborhood,
                        "price": price,
                        "address": address,
                        "beds": beds,
                        "baths": baths,
                        "sqft": sqft,
                        "property_type": self.current_property_type,
                    }
                )
            except Exception as e:
                print(f"Error extracting Apartments.com data from card: {e}")
                continue

        return properties
