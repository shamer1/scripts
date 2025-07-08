import requests
from scraper.doordash_scraper import DoorDashScraper

def main():
    url = "https://devconsole.doordash.team/storage-self-serve/crdb/cluster-health?checkResult=fail&startDate=2025-07-08&endDate=2025-07-09"
    scraper = DoorDashScraper(url)
    
    try:
        data = scraper.scrape()
        print("Scraped Data:")
        print(data)
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()