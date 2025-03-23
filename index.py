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

class NYCHousingScraper:
    def __init__(self, headless=True):
        # Setup Chrome options
        chrome_options = Options()

        if headless:
            chrome_options.add_argument("--headless")

        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)

        # Initialize webdriver
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )

        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

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
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
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

    # ZILLOW SPECIFIC METHODS
    def scrape_zillow_neighborhood(self, neighborhood_name, url, property_type="rent", max_pages=3):
        """Scrape Zillow listings for a specific neighborhood"""
        print(f"Scraping Zillow - {neighborhood_name}...")
        self.current_neighborhood = neighborhood_name
        self.current_property_type = property_type
        self.current_source = "zillow"

        # Construct search URL
        if property_type == "rent":
            search_url = f"{url}rentals/"
        else:
            search_url = f"{url}houses/"

        self.driver.get(search_url)
        time.sleep(random.uniform(3, 5))

        # Wait for page to load
        try:
            selectors = ["ul.photo-cards", "div[data-testid='search-list']", "div.search-page-list-container"]
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
            # Extract properties from current page
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            properties = self.extract_zillow_properties(soup)
            all_properties.extend(properties)

            print(f"Zillow - Page {current_page}: Extracted {len(properties)} properties")

            # Check if there's a next page button
            try:
                pagination_options = [
                    "a[title='Next page']",
                    "a.zsg-pagination-next",
                    "a.PaginationButton-c11n-8-84-3__sc-10d5vzb-0",
                    "button[aria-label='Next page']",
                    "li.PaginationJumpItem-c11n-8-84-3__sc-18wdg2l-0:last-child a"
                ]

                next_page_found = False
                for selector in pagination_options:
                    next_page_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if next_page_elements and len(next_page_elements) > 0:
                        if "disabled" not in next_page_elements[0].get_attribute("class").lower():
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

    def extract_zillow_properties(self, soup):
        """Extract property data from Zillow's HTML"""
        property_selectors = [
            "ul.photo-cards > li",
            "div[data-testid='search-list'] > ul > li",
            "div.StyledPropertyCardDataWrapper",
            "div[data-test='property-card']"
        ]

        property_cards = []
        for selector in property_selectors:
            cards = soup.select(selector)
            if cards:
                property_cards = cards
                break

        if not property_cards:
            print("No Zillow property cards found with known selectors")

        properties = []
        for card in property_cards:
            try:
                # For price
                price_selectors = [
                    "div.list-card-price",
                    "span.PropertyCardWrapper__StyledPriceLine",
                    "span[data-test='property-card-price']"
                ]
                price = self.try_selectors(card, price_selectors)

                # For address
                address_selectors = [
                    "address.list-card-addr",
                    "address[data-test='property-card-addr']",
                    "a.property-card-link address"
                ]
                address = self.try_selectors(card, address_selectors)

                # For details (beds, baths, sqft)
                beds, baths, sqft = "N/A", "N/A", "N/A"

                details_selectors = [
                    "ul.list-card-details li",
                    "div[data-test='property-card-details'] span",
                    "ul.StyledPropertyCardHomeDetailsList li"
                ]

                for selector in details_selectors:
                    details = card.select(selector)
                    if details and len(details) > 0:
                        for detail in details:
                            text = detail.text.strip().lower()
                            if "bd" in text or "bed" in text:
                                beds = text
                            elif "ba" in text or "bath" in text:
                                baths = text
                            elif "sqft" in text or "sq ft" in text:
                                sqft = text

                # Only add if we found at least price or address
                if price or address:
                    properties.append({
                        "source": "zillow",
                        "neighborhood": self.current_neighborhood,
                        "price": price or "N/A",
                        "address": address or "N/A",
                        "beds": beds,
                        "baths": baths,
                        "sqft": sqft,
                        "property_type": self.current_property_type
                    })
            except Exception as e:
                print(f"Error extracting Zillow data from card: {e}")
                continue

        return properties

    # STREETEASY SPECIFIC METHODS
    def scrape_streeteasy_neighborhood(self, neighborhood_name, property_type="rent", max_pages=3):
        """Scrape StreetEasy listings for a specific neighborhood"""
        print(f"Scraping StreetEasy - {neighborhood_name}...")
        self.current_neighborhood = neighborhood_name
        self.current_property_type = property_type
        self.current_source = "streeteasy"

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
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.SearchResultsListingsContainer"))
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
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            properties = self.extract_streeteasy_properties(soup)
            all_properties.extend(properties)

            print(f"StreetEasy - Page {current_page}: Extracted {len(properties)} properties")

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

    def extract_streeteasy_properties(self, soup):
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
                    bed_match = re.search(r'(\d+)\s*bed', details_text, re.IGNORECASE)
                    if bed_match:
                        beds = f"{bed_match.group(1)} bed"

                    # Extract bathrooms
                    bath_match = re.search(r'(\d+)\s*bath', details_text, re.IGNORECASE)
                    if bath_match:
                        baths = f"{bath_match.group(1)} bath"

                    # Extract square footage
                    sqft_match = re.search(r'(\d+,?\d*)\s*ft²', details_text)
                    if sqft_match:
                        sqft = f"{sqft_match.group(1)} sqft"

                properties.append({
                    "source": "streeteasy",
                    "neighborhood": self.current_neighborhood,
                    "price": price,
                    "address": address,
                    "beds": beds,
                    "baths": baths,
                    "sqft": sqft,
                    "property_type": self.current_property_type
                })
            except Exception as e:
                print(f"Error extracting StreetEasy data from card: {e}")
                continue

        return properties

    # APARTMENTS.COM SPECIFIC METHODS
    def scrape_apartments_neighborhood(self, neighborhood_name, property_type="rent", max_pages=3):
        """Scrape Apartments.com listings for a specific neighborhood"""
        print(f"Scraping Apartments.com - {neighborhood_name}...")
        self.current_neighborhood = neighborhood_name
        self.current_property_type = property_type
        self.current_source = "apartments.com"

        # Apartments.com has different URL structure
        neighborhood_formatted = neighborhood_name.replace("-", "-").lower()

        # Apartments.com only has rentals
        search_url = f"https://www.apartments.com/new-york/{neighborhood_formatted}/"

        self.driver.get(search_url)
        time.sleep(random.uniform(3, 5))

        # Wait for page to load
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.placardContainer"))
            )
        except:
            print(f"Timeout or error loading {search_url}")
            return []

        self.scroll_page(scroll_pauses=8)  # More scrolling for apartments.com

        # Extract properties (pagination works differently on apartments.com)
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        properties = self.extract_apartments_properties(soup)

        print(f"Apartments.com: Extracted {len(properties)} properties")

        return properties

    def extract_apartments_properties(self, soup):
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

                properties.append({
                    "source": "apartments.com",
                    "neighborhood": self.current_neighborhood,
                    "price": price,
                    "address": address,
                    "beds": beds,
                    "baths": baths,
                    "sqft": sqft,
                    "property_type": self.current_property_type
                })
            except Exception as e:
                print(f"Error extracting Apartments.com data from card: {e}")
                continue

        return properties

    # NEIGHBORHOOD DEFINITIONS
    def get_neighborhoods(self):
        """Get URLs for each NYC neighborhood"""
        manhattan_neighborhoods = {
            "upper-east-side": "https://www.zillow.com/upper-east-side-new-york-ny/",
            "upper-west-side": "https://www.zillow.com/upper-west-side-new-york-ny/",
            "midtown": "https://www.zillow.com/midtown-new-york-ny/",
            "chelsea": "https://www.zillow.com/chelsea-new-york-ny/",
            "greenwich-village": "https://www.zillow.com/greenwich-village-new-york-ny/",
            "east-village": "https://www.zillow.com/east-village-new-york-ny/",
            "harlem": "https://www.zillow.com/harlem-new-york-ny/",
            "tribeca": "https://www.zillow.com/tribeca-new-york-ny/",
            "soho": "https://www.zillow.com/soho-new-york-ny/"
        }

        brooklyn_neighborhoods = {
            "williamsburg": "https://www.zillow.com/williamsburg-new-york-ny/",
            "park-slope": "https://www.zillow.com/park-slope-new-york-ny/",
            "brooklyn-heights": "https://www.zillow.com/brooklyn-heights-new-york-ny/",
            "dumbo": "https://www.zillow.com/dumbo-new-york-ny/",
            "bushwick": "https://www.zillow.com/bushwick-new-york-ny/",
            "bedford-stuyvesant": "https://www.zillow.com/bedford-stuyvesant-new-york-ny/"
        }

        # Add more neighborhoods as needed
        all_neighborhoods = {}
        all_neighborhoods.update(manhattan_neighborhoods)
        all_neighborhoods.update(brooklyn_neighborhoods)

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
            neighborhood_items = list(neighborhoods.items())[:max_neighborhoods]
            neighborhoods = dict(neighborhood_items)

        # Scrape each neighborhood from each source
        for name, zillow_url in neighborhoods.items():
            try:
                # Zillow
                if "zillow" in sources:
                    properties = self.scrape_zillow_neighborhood(name, zillow_url, property_type)
                    all_properties.extend(properties)
                    time.sleep(random.uniform(5, 10))

                # StreetEasy
                if "streeteasy" in sources:
                    properties = self.scrape_streeteasy_neighborhood(name, property_type)
                    all_properties.extend(properties)
                    time.sleep(random.uniform(5, 10))

                # Apartments.com (only for rentals)
                if "apartments" in sources and property_type == "rent":
                    properties = self.scrape_apartments_neighborhood(name, property_type)
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
        df['price_clean'] = df['price'].str.replace('$', '').str.replace(',', '')
        df['price_clean'] = df['price_clean'].str.replace('/mo', '').str.replace('+', '')
        df['price_clean'] = df['price_clean'].str.replace('From', '').str.strip()

        # Extract the first number in case of ranges
        df['price_clean'] = df['price_clean'].apply(
            lambda x: re.search(r'(\d+)', str(x)).group(1) if isinstance(x, str) and re.search(r'(\d+)', x) else x
        )

        df['price_clean'] = pd.to_numeric(df['price_clean'], errors='coerce')

        # Clean sqft data
        df['sqft_clean'] = df['sqft'].str.replace('sqft', '').str.replace('ft²', '').str.replace(',', '').str.strip()
        df['sqft_clean'] = df['sqft_clean'].apply(
            lambda x: re.search(r'(\d+)', str(x)).group(1) if isinstance(x, str) and re.search(r'(\d+)', x) else x
        )
        df['sqft_clean'] = pd.to_numeric(df['sqft_clean'], errors='coerce')

        # Calculate price per sqft where available
        df['price_per_sqft'] = df.apply(
            lambda x: x['price_clean'] / x['sqft_clean'] if pd.notnull(x['sqft_clean']) and x['sqft_clean'] > 0 else None,
            axis=1
        )

        # Calculate overall stats per neighborhood (across all sources)
        overall_stats = df.groupby('neighborhood').agg({
            'price_clean': ['mean', 'median', 'min', 'max', 'count'],
            'price_per_sqft': ['mean', 'median', 'min', 'max', 'count'],
        })

        # Flatten the column hierarchy
        overall_stats.columns = ['overall_' + '_'.join(col).strip() for col in overall_stats.columns.values]

        # Calculate stats per source per neighborhood
        source_stats = df.groupby(['neighborhood', 'source']).agg({
            'price_clean': ['mean', 'median', 'count'],
        })

        # Restructure the source stats to have source in the column names
        source_stats_reshaped = pd.DataFrame()
        for (neighborhood, source), group in source_stats.groupby(level=[0, 1]):
            for col in group.columns:
                new_col = f"{source}_{col[0]}_{col[1]}"
                source_stats_reshaped.loc[neighborhood, new_col] = group.loc[(neighborhood, source), col]

        # Combine overall and source-specific stats
        combined_stats = pd.concat([overall_stats, source_stats_reshaped], axis=1)

        # Add count of listings by property size
        bed_counts = df.groupby(['neighborhood', 'beds']).size().unstack(fill_value=0)
        bed_counts.columns = [f'count_{col}_bed' for col in bed_counts.columns]

        combined_stats = pd.concat([combined_stats, bed_counts], axis=1)

        # Save to CSV
        filename = f"nyc_multi_source_stats_{time.strftime('%Y%m%d')}.csv"
        combined_stats.to_csv(filename)
        print(f"Saved combined stats to {filename}")

        return combined_stats

    def close(self):
        """Close the webdriver"""
        self.driver.quit()


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
            max_neighborhoods=3  # Limit for testing
        )

        # Calculate combined statistics
        combined_stats = scraper.calculate_combined_stats(rental_data)

    finally:
        scraper.close()
