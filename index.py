import time
import pandas as pd
import random
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

MANHATTAN_NEIGHBORHOODS = [
    "upper-east-side",
    "upper-west-side",
    "midtown",
    "chelsea",
    "greenwich-village",
    "east-village",
    "harlem",
    "tribeca",
    "soho",
]

BROOKLYN_NEIGHBORHOODS = [
    "williamsburg",
    "park-slope",
    "brooklyn-heights",
    "dumbo",
    "bushwick",
    "bedford-stuyvesant",
]


class ZillowScraper:
    def __init__(self, headless=True):
        # Setup Chrome options
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")

        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15"
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

        # Execute CDP commands to modify navigator properties
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            """
        })

        # Base URL for Zillow NYC searches
        self.base_url = "https://www.zillow.com/new-york-ny"

    def get_neighborhood_url(self, neighborhood_name):
        """Get URL for a specific NYC neighborhood based on the base URL"""
        # Format the neighborhood name for the URL
        formatted_neighborhood = neighborhood_name.replace(" ", "-").lower()
        # Construct the full URL with the base URL and neighborhood name
        neighborhood_url = (
            f"{self.base_url.rstrip('/')}/{formatted_neighborhood}-new-york-ny"
        )
        return neighborhood_url

    def scroll_page(self, scroll_pauses=5, scroll_increment=800):
        """Scroll down the page to load all properties"""
        # Get scroll height
        last_height = self.driver.execute_script("return document.body.scrollHeight")

        for i in range(scroll_pauses):
            # Scroll down incrementally
            self.driver.execute_script(f"window.scrollBy(0, {scroll_increment});")

            # Wait to load page
            time.sleep(random.uniform(1, 2))

            # Calculate new scroll height and compare with last scroll height
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                # Try one more scroll to ensure we've reached bottom
                self.driver.execute_script(
                    "window.scrollTo(0, document.body.scrollHeight);"
                )
                time.sleep(random.uniform(1, 2))
                new_height = self.driver.execute_script(
                    "return document.body.scrollHeight"
                )
                if new_height == last_height:
                    break
            last_height = new_height

            # Random delay to appear more human-like
            time.sleep(random.uniform(0.5, 1.5))

    def handle_pagination(self, max_pages=5):
        """Navigate through multiple pages of results"""
        all_properties = []
        current_page = 1

        while current_page <= max_pages:
            print(f"Zillow - Extracting page {current_page}")
            # Extract properties from current page
            soup = BeautifulSoup(self.driver.page_source, "html.parser")
            properties = self.extract_properties_from_page(soup)
            all_properties.extend(properties)

            print(f"Page {current_page}: Extracted {len(properties)} properties")

            # Check if there's a next page button
            try:
                # Zillow's pagination structure changes frequently
                # Here are some common selectors to try:
                pagination_options = [
                    "a[rel='next'][title='Next page']",
                    "a.zsg-pagination-next",
                    "a.PaginationButton-c11n-8-84-3__sc-10d5vzb-0",  # Current as of coding
                    "button[aria-label='Next page']",
                    "li.PaginationJumpItem-c11n-8-84-3__sc-18wdg2l-0:last-child a",
                ]

                next_page_found = False
                for selector in pagination_options:
                    next_page_elements = self.driver.find_elements(
                        By.CSS_SELECTOR, selector
                    )
                    if next_page_elements and len(next_page_elements) > 0:
                        # Check if the button is disabled
                        if (
                            "disabled"
                            not in next_page_elements[0].get_attribute("class").lower()
                        ):
                            next_page_elements[0].click()
                            next_page_found = True
                            break

                if not next_page_found:
                    print("No more pages available")
                    break

                # Wait for the next page to load
                time.sleep(random.uniform(3, 5))

                # Wait for element that indicates the page is loaded
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, "ul.photo-cards")
                        )
                    )
                except:
                    print("Timeout waiting for next page to load")
                    break

                # Scroll the new page
                self.scroll_page()
                current_page += 1

            except Exception as e:
                print(f"Error navigating to next page: {e}")
                break

        return all_properties

    def extract_properties_from_page(self, soup):
        """Extract property data from the current page's HTML"""
        # Zillow changes their HTML structure frequently, so adjust these selectors as needed
        property_card_selector = "div.property-card-data"

        property_cards = []
        cards = soup.select(property_card_selector)
        if cards:
            property_cards = cards

        if not property_cards:
            print("No property cards found with known selectors")

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
                address_selectors = ["address"]
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

    def scrape_neighborhood(self, neighborhood_name, property_type="rent"):
        """Scrape property listings for a specific neighborhood"""
        print(f"Scraping {neighborhood_name}...")

        # Store current context for use in other methods
        self.current_neighborhood = neighborhood_name
        self.current_property_type = property_type

        url = self.get_neighborhood_url(neighborhood_name)

        # Construct the search URL based on property type
        if property_type == "rent":
            search_url = f"{url}/rentals/"
        else:
            search_url = f"{url}/houses/"

        self.driver.get(search_url)
        # time.sleep(random.uniform(3, 5))  # Random delay to avoid detection
        time.sleep(50)  # Random delay to avoid detection

        # Check if access has been denied
        page_title = self.driver.title
        if "Access to this page has been denied" in page_title:
            print(f"Access denied error when loading {search_url}")
            return []

        # Wait for the page to load
        try:
            selector = "div.search-page-lst-container"
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
        except:
            print(f"Timeout or error loading {search_url}")
            return []

        # Scroll down to load all properties on the first page
        self.scroll_page()

        # Handle pagination and get all properties
        return self.handle_pagination(
            max_pages=1
        )  # Limit to 3 pages per neighborhood for example

    # The rest of the methods same as before...
    def get_detailed_neighborhoods(self):
        """Get more detailed NYC neighborhoods beyond the 5 boroughs"""
        detailed_neighborhoods = []
        detailed_neighborhoods.extend(MANHATTAN_NEIGHBORHOODS)
        detailed_neighborhoods.extend(BROOKLYN_NEIGHBORHOODS)
        return detailed_neighborhoods

    def run_scraper(self, property_type="rent", use_detailed=True):
        """Run the scraper for all neighborhoods"""
        all_properties = []

        neighborhoods = self.get_detailed_neighborhoods()

        # Scrape each neighborhood
        for name in neighborhoods:
            try:
                properties = self.scrape_neighborhood(name, property_type)
                all_properties.extend(properties)

                # Random delay between neighborhood scrapes
                time.sleep(random.uniform(5, 10))
            except Exception as e:
                print(f"Error scraping {name}: {e}")
                continue

        # Convert to DataFrame and save to CSV
        df = pd.DataFrame(all_properties)
        filename = f"nyc_{property_type}_prices_{time.strftime('%Y%m%d')}.csv"
        df.to_csv(filename, index=False)
        print(f"Saved data to {filename}")

        return df

    def calculate_neighborhood_stats(self, df):
        """Calculate average prices and other stats by neighborhood"""
        # Clean price data - remove $ and convert to float
        df["price_clean"] = (
            df["price"]
            .str.replace("$", "")
            .str.replace(",", "")
            .str.replace("/mo", "")
            .str.replace("+", "")
        )
        df["price_clean"] = pd.to_numeric(df["price_clean"], errors="coerce")

        # Clean sqft data
        df["sqft_clean"] = (
            df["sqft"].str.replace("sqft", "").str.replace(",", "").str.strip()
        )
        df["sqft_clean"] = pd.to_numeric(df["sqft_clean"], errors="coerce")

        # Calculate price per sqft where available
        df["price_per_sqft"] = df.apply(
            lambda x: x["price_clean"] / x["sqft_clean"]
            if pd.notnull(x["sqft_clean"]) and x["sqft_clean"] > 0
            else None,
            axis=1,
        )

        # Group by neighborhood and calculate stats
        neighborhood_stats = df.groupby("neighborhood").agg(
            {
                "price_clean": ["mean", "median", "min", "max", "count"],
                "price_per_sqft": ["mean", "median", "min", "max", "count"],
                "beds": lambda x: x.value_counts().index[0]
                if len(x.value_counts()) > 0
                else None,
                "baths": lambda x: x.value_counts().index[0]
                if len(x.value_counts()) > 0
                else None,
            }
        )

        # Flatten the column hierarchy
        neighborhood_stats.columns = [
            "_".join(col).strip() for col in neighborhood_stats.columns.values
        ]

        # Save to CSV
        filename = f"nyc_neighborhood_stats_{time.strftime('%Y%m%d')}.csv"
        neighborhood_stats.to_csv(filename)
        print(f"Saved neighborhood stats to {filename}")

        return neighborhood_stats

    def close(self):
        """Close the webdriver"""
        self.driver.quit()


# Example usage
if __name__ == "__main__":
    scraper = ZillowScraper(headless=False)

    try:
        # Scrape rental properties
        rental_data = scraper.run_scraper(property_type="rent", use_detailed=True)

        # Calculate neighborhood statistics
        rental_stats = scraper.calculate_neighborhood_stats(rental_data)

    finally:
        scraper.close()
