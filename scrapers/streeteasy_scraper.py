import time
import random
import re
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from scrapers.base_scraper import BaseScraper


class StreetEasyScraper(BaseScraper):
    def __init__(self, headless=True):
        super().__init__(headless)
        self.current_source = "streeteasy"

    def scrape_neighborhood(self, neighborhood_name, property_type="rent", max_pages=3):
        """Scrape StreetEasy listings for a specific neighborhood"""
        print(f"Scraping StreetEasy - {neighborhood_name}...")
        self.current_neighborhood = neighborhood_name
        self.current_property_type = property_type

        # StreetEasy has different URL structure
        neighborhood_formatted = neighborhood_name.replace("-", "_")

        if property_type == "rent":
            search_url = f"https://streeteasy.com/for-rent/{neighborhood_formatted}"
        else:
            search_url = f"https://streeteasy.com/for-sale/{neighborhood_formatted}"

        self.driver.get(search_url)
        time.sleep(random.uniform(3, 5))

        # Wait for page to load
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div.SearchResultsListingsContainer")
                )
            )
        except:
            print(f"Timeout or error loading {search_url}")
            return []

        self.scroll_page()

        # Handle pagination and extract properties
        all_properties = []
        current_page = 1

        while current_page <= max_pages:
            # Extract properties from current page
            soup = BeautifulSoup(self.driver.page_source, "html.parser")
            properties = self.extract_properties(soup)
            all_properties.extend(properties)

            print(
                f"StreetEasy - Page {current_page}: Extracted {len(properties)} properties"
            )

            # Check if there's a next page button
            try:
                next_button = self.driver.find_element(By.CSS_SELECTOR, "a.next_page")
                if next_button:
                    next_button.click()
                    time.sleep(random.uniform(3, 5))
                    self.scroll_page()
                    current_page += 1
                else:
                    print("No more StreetEasy pages available")
                    break
            except Exception as e:
                print(f"Error navigating to next StreetEasy page: {e}")
                break

        return all_properties

    def extract_properties(self, soup):
        """Extract property data from StreetEasy's HTML"""
        property_cards = soup.select("div.searchCardList--listItem")

        properties = []
        for card in property_cards:
            try:
                # Price
                price_elem = card.select_one("span.price")
                price = price_elem.text.strip() if price_elem else "N/A"

                # Address
                address_elem = card.select_one("address.listingCard-addressLabel")
                address = address_elem.text.strip() if address_elem else "N/A"

                # Details
                details_elem = card.select_one("div.listingCard-keyDetails")
                beds, baths, sqft = "N/A", "N/A", "N/A"

                if details_elem:
                    details_text = details_elem.text.strip()

                    # Extract bedrooms
                    bed_match = re.search(r"(\d+)\s*bed", details_text, re.IGNORECASE)
                    if bed_match:
                        beds = f"{bed_match.group(1)} bed"

                    # Extract bathrooms
                    bath_match = re.search(r"(\d+)\s*bath", details_text, re.IGNORECASE)
                    if bath_match:
                        baths = f"{bath_match.group(1)} bath"

                    # Extract square footage
                    sqft_match = re.search(r"(\d+,?\d*)\s*ft²", details_text)
                    if sqft_match:
                        sqft = f"{sqft_match.group(1)} sqft"

                properties.append(
                    {
                        "source": "streeteasy",
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
                print(f"Error extracting StreetEasy data from card: {e}")
                continue

        return properties
