import time
import random
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from scrapers.base_scraper import BaseScraper


class ZillowScraper(BaseScraper):
    def __init__(self, headless=True):
        super().__init__(headless)
        self.current_source = "zillow"
        self.base_url = "https://www.zillow.com"

    def get_neighborhood_url(self, neighborhood_name):
        """Get URL for a specific NYC neighborhood based on the base URL"""
        # Format the neighborhood name for the URL
        formatted_neighborhood = neighborhood_name.replace(" ", "-").lower()
        # Construct the full URL with the base URL and neighborhood name
        neighborhood_url = (
            f"{self.base_url.rstrip('/')}/{formatted_neighborhood}-new-york-ny"
        )
        return neighborhood_url

    def scrape_neighborhood(self, neighborhood_name, property_type="rent", max_pages=3):
        """Scrape Zillow listings for a specific neighborhood"""
        self.current_neighborhood = neighborhood_name
        self.current_property_type = property_type
        neighborhood_url = self.get_neighborhood_url(neighborhood_name)

        # Construct search URL
        if property_type == "rent":
            search_url = f"{neighborhood_url}/rentals"
        else:
            search_url = f"{neighborhood_url}/houses"

        print(f"searching url: {search_url}")

        self.driver.get(search_url)
        time.sleep(random.uniform(3, 5))

        # Check if access has been denied
        page_title = self.driver.title
        if "Access to this page has been denied" in page_title:
            print(f"Access denied error when loading {search_url}")
            return []

        # Wait for page to load
        try:
            selectors = [
                "ul.photo-cards",
                "div.search-page-lst-container",
                # "div[data-testid='search-list']",
            ]
            for selector in selectors:
                try:
                    WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    break
                except:
                    continue
        except:
            print(f"Timeout or error loading {search_url}")
            return []

        self.scroll_page()
        # Handle pagination and extract properties
        all_properties = []
        current_page = 1

        while current_page <= max_pages:
            print(f"Zillow - Extracting page {current_page}")

            # Extract properties from current page
            soup = BeautifulSoup(self.driver.page_source, "html.parser")
            properties = self.extract_properties(soup)
            all_properties.extend(properties)

            print(
                f"Zillow - Page {current_page}: Extracted {len(properties)} properties"
            )

            # Check if there's a next page button
            try:
                pagination_selector = "a[rel='next'][title='Next page']"

                next_page_found = False
                next_page_elements = self.driver.find_elements(
                    By.CSS_SELECTOR, pagination_selector
                )
                if next_page_elements and len(next_page_elements) > 0:
                    # Check if the next button is disabled
                    if "disabled" not in next_page_elements[0].get_attribute(
                        "aria-disabled"
                    ).lower() and "true" != next_page_elements[0].get_attribute(
                        "aria-disabled"
                    ):
                        next_page_elements[0].click()
                        next_page_found = True
                        break

                if not next_page_found:
                    print("No more Zillow pages available")
                    break

                time.sleep(random.uniform(3, 5))
                self.scroll_page()
                current_page += 1

            except Exception as e:
                print(f"Error navigating to next Zillow page: {e}")
                break

        return all_properties

    def extract_properties(self, soup):
        """Extract property data from Zillow's HTML"""
        property_selectors = ["div.property-card-data"]

        property_cards = []
        for selector in property_selectors:
            cards = soup.select(selector)
            if cards:
                property_cards = cards
                break

        if not property_cards:
            print("No Zillow property cards found with known selectors")

        properties = []
        for i, card in enumerate(property_cards):
            print(f"Processing Zillow property card {i+1}/{len(property_cards)}")
            try:
                # For price
                price_selectors = [
                    "span[data-test='property-card-price']",
                ]
                price = self.try_selectors(card, price_selectors)

                # For address
                address_selectors = [
                    "address"
                    # "address.list-card-addr",
                    # "address[data-test='property-card-addr']",
                    # "a.property-card-link address",
                ]
                address = self.try_selectors(card, address_selectors)

                # For details (beds, baths, sqft)
                beds, baths, sqft = "N/A", "N/A", "N/A"

                details_selector = (
                    "ul.StyledPropertyCardHomeDetailsList-c11n-8-109-3__sc-1j0som5-0"
                )
                details_element = card.select_one(details_selector)

                if details_element:
                    # Process list items within the ul
                    list_items = details_element.select("li")
                    for item in list_items:
                        item_text = item.text.strip()

                        # Check for Studio
                        if "Studio" in item_text:
                            beds = "Studio"
                        # Check for bedroom info (usually has b tag)
                        elif (
                            item.select_one("b")
                            and "ba" not in item_text.lower()
                            and "sqft" not in item_text.lower()
                        ):
                            beds = item.select_one("b").text.strip() + " bed"
                        # Check for bathroom info
                        elif "ba" in item_text.lower():
                            baths = (
                                item.select_one("b").text.strip() + " ba"
                                if item.select_one("b")
                                else item_text
                            )
                        # Check for square footage
                        elif "sqft" in item_text.lower():
                            sqft = (
                                item.select_one("b").text.strip() + " sqft"
                                if item.select_one("b")
                                else item_text
                            )

                # Only add if we found at least price or address
                if price or address:
                    properties.append(
                        {
                            "source": "zillow",
                            "neighborhood": self.current_neighborhood,
                            "price": price or "N/A",
                            "address": address or "N/A",
                            "beds": beds,
                            "baths": baths,
                            "sqft": sqft,
                            "property_type": self.current_property_type,
                        }
                    )
            except Exception as e:
                print(f"Error extracting Zillow data from card: {e}")
                continue

        return properties
