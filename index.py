import time
import pandas as pd
import random
import re
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
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


class NYCHousingScraper:
    def __init__(self, headless=True):
        self.headless = headless
        self.zillow_scraper = ZillowScraper(headless)
        self.streeteasy_scraper = StreetEasyScraper(headless)
        self.apartments_scraper = ApartmentsScraper(headless)

    def get_neighborhoods(self):
        # Add more neighborhoods as needed
        all_neighborhoods = []
        all_neighborhoods.extend(MANHATTAN_NEIGHBORHOODS)
        all_neighborhoods.extend(BROOKLYN_NEIGHBORHOODS)
        return all_neighborhoods

    # MAIN SCRAPING METHOD
    def run_scraper(self, property_type="rent", sources=None, max_neighborhoods=None):
        """Run the scraper for all sources and neighborhoods"""
        if sources is None:
            sources = ["zillow", "streeteasy", "apartments"]

        all_properties = []
        neighborhoods = self.get_neighborhoods()

        # Limit the number of neighborhoods if specified
        if max_neighborhoods and max_neighborhoods < len(neighborhoods):
            neighborhoods = neighborhoods[:max_neighborhoods]

        # Scrape each neighborhood from each source
        for name in neighborhoods:
            try:
                # Zillow
                if "zillow" in sources:
                    print(f"Scraping Zillow :: {name} :: {property_type} ")
                    properties = self.zillow_scraper.scrape_neighborhood(
                        name, property_type
                    )
                    all_properties.extend(properties)
                    time.sleep(random.uniform(5, 10))

                # StreetEasy
                if "streeteasy" in sources:
                    print(f"Scraping StreetEasy :: {name} :: {property_type} ")
                    properties = self.streeteasy_scraper.scrape_neighborhood(
                        name, property_type
                    )
                    all_properties.extend(properties)
                    time.sleep(random.uniform(5, 10))

                # Apartments.com (only for rentals)
                if "apartments" in sources and property_type == "rent":
                    properties = self.apartments_scraper.scrape_neighborhood(
                        name, property_type
                    )
                    all_properties.extend(properties)
                    time.sleep(random.uniform(5, 10))

            except Exception as e:
                print(f"Error scraping {name}: {e}")
                continue

        # Convert to DataFrame and save to CSV
        df = pd.DataFrame(all_properties)
        filename = f"nyc_{property_type}_prices_combined_{time.strftime('%Y%m%d')}.csv"
        df.to_csv(filename, index=False)
        print(f"Saved data to {filename}")

        return df

    def calculate_combined_stats(self, df):
        """Calculate average prices and other stats by neighborhood with source tracking"""
        # Clean price data from different formats
        df["price_clean"] = df["price"].str.replace("$", "").str.replace(",", "")
        df["price_clean"] = (
            df["price_clean"].str.replace("/mo", "").str.replace("+", "")
        )
        df["price_clean"] = df["price_clean"].str.replace("From", "").str.strip()

        # Extract the first number in case of ranges
        df["price_clean"] = df["price_clean"].apply(
            lambda x: re.search(r"(\d+)", str(x)).group(1)
            if isinstance(x, str) and re.search(r"(\d+)", x)
            else x
        )

        df["price_clean"] = pd.to_numeric(df["price_clean"], errors="coerce")

        # Clean sqft data
        df["sqft_clean"] = (
            df["sqft"]
            .str.replace("sqft", "")
            .str.replace("ft²", "")
            .str.replace(",", "")
            .str.strip()
        )
        df["sqft_clean"] = df["sqft_clean"].apply(
            lambda x: re.search(r"(\d+)", str(x)).group(1)
            if isinstance(x, str) and re.search(r"(\d+)", x)
            else x
        )
        df["sqft_clean"] = pd.to_numeric(df["sqft_clean"], errors="coerce")

        # Calculate price per sqft where available
        df["price_per_sqft"] = df.apply(
            lambda x: x["price_clean"] / x["sqft_clean"]
            if pd.notnull(x["sqft_clean"]) and x["sqft_clean"] > 0
            else None,
            axis=1,
        )

        # Calculate overall stats per neighborhood (across all sources)
        overall_stats = df.groupby("neighborhood").agg(
            {
                "price_clean": ["mean", "median", "min", "max", "count"],
                "price_per_sqft": ["mean", "median", "min", "max", "count"],
            }
        )

        # Flatten the column hierarchy
        overall_stats.columns = [
            "overall_" + "_".join(col).strip() for col in overall_stats.columns.values
        ]

        # Calculate stats per source per neighborhood
        source_stats = df.groupby(["neighborhood", "source"]).agg(
            {
                "price_clean": ["mean", "median", "count"],
            }
        )

        # Restructure the source stats to have source in the column names
        source_stats_reshaped = pd.DataFrame()
        for (neighborhood, source), group in source_stats.groupby(level=[0, 1]):
            for col in group.columns:
                new_col = f"{source}_{col[0]}_{col[1]}"
                source_stats_reshaped.loc[neighborhood, new_col] = group.loc[
                    (neighborhood, source), col
                ]

        # Combine overall and source-specific stats
        combined_stats = pd.concat([overall_stats, source_stats_reshaped], axis=1)

        # Add count of listings by property size
        bed_counts = df.groupby(["neighborhood", "beds"]).size().unstack(fill_value=0)
        bed_counts.columns = [f"count_{col}_bed" for col in bed_counts.columns]

        combined_stats = pd.concat([combined_stats, bed_counts], axis=1)

        # Save to CSV
        filename = f"nyc_multi_source_stats_{time.strftime('%Y%m%d')}.csv"
        combined_stats.to_csv(filename)
        print(f"Saved combined stats to {filename}")

        return combined_stats

    def close(self):
        """Close all webdrivers"""
        self.zillow_scraper.close()
        self.streeteasy_scraper.close()
        self.apartments_scraper.close()


# Example usage
if __name__ == "__main__":
    scraper = NYCHousingScraper(headless=True)

    try:
        # For testing, scrape a limited number of neighborhoods
        # In production, remove the max_neighborhoods parameter
        rental_data = scraper.run_scraper(
            property_type="rent",
            # sources=["zillow", "streeteasy", "apartments"],
            sources=["zillow"],
            max_neighborhoods=3,  # Limit for testing
        )

        # Calculate combined statistics
        combined_stats = scraper.calculate_combined_stats(rental_data)

    finally:
        scraper.close()
