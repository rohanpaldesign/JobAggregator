import json
import time
import requests
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# ------------- CONFIGURATION -------------
# Load companies configuration from companies.json
with open("companies.json", "r") as f:
    companies = json.load(f)

# Airtable configuration: Replace these with your actual Personal Access Token (PAT) and Base ID.
# For Airtable now, generate a Personal Access Token from your Airtable account settings.
AIRTABLE_PAT = os.getenv("AIRTABLE_PAT") or "YOUR_AIRTABLE_PERSONAL_ACCESS_TOKEN"
BASE_ID = os.getenv("BASE_ID") or "YOUR_BASE_ID"
TABLE_NAME = "Jobs"
# Use the PAT in the Authorization header as "Bearer <PAT>"
AIRTABLE_URL = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_NAME}"
HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_PAT}",
    "Content-Type": "application/json"
}

# ------------- FUNCTIONS -------------
def init_selenium_driver():
    """Initializes a headless Chrome driver using Selenium."""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    driver = webdriver.Chrome(ChromeDriverManager().install(), options=options)
    return driver

def scrape_company(company_conf):
    """Scrapes job postings for a single company based on its configuration.
       Uses Selenium for dynamic pages; static pages can be handled similarly with requests/BeautifulSoup.
    """
    company = company_conf["company"]
    url = company_conf["url"]
    selectors = company_conf["selectors"]
    job_list = []
    print(f"Scraping {company} at {url}")

    if company_conf["type"] == "dynamic":
        driver = init_selenium_driver()
        driver.get(url)
        time.sleep(5)  # Wait for dynamic content to load; adjust if needed.
        job_cards = driver.find_elements(By.CSS_SELECTOR, selectors["job_card"])
        for card in job_cards:
            try:
                title = card.find_element(By.CSS_SELECTOR, selectors["job_title"]).text.strip()
                location = card.find_element(By.CSS_SELECTOR, selectors["job_location"]).text.strip()
                apply_elem = card.find_element(By.CSS_SELECTOR, selectors["apply_url"])
                apply_url = apply_elem.get_attribute("href")
                job_list.append({
                    "Company": company,
                    "Job Title": title,
                    "Location": location,
                    "Apply URL": apply_url,
                    "Last Updated": datetime.utcnow().isoformat()
                })
            except Exception as e:
                print(f"Error parsing job card for {company}: {e}")
        driver.quit()
    else:
        print(f"Static scraping for {company} is not implemented in this template.")
    return job_list

def get_airtable_jobs():
    """Retrieves current job postings from Airtable.
       Uses a unique key (Company|Job Title|Apply URL) to map each job.
    """
    response = requests.get(AIRTABLE_URL, headers=HEADERS)
    if response.status_code == 200:
        data = response.json()
        airtable_jobs = {}
        for record in data.get("records", []):
            fields = record["fields"]
            key = f"{fields.get('Company')}|{fields.get('Job Title')}|{fields.get('Apply URL')}"
            airtable_jobs[key] = record["id"]
        return airtable_jobs
    else:
        print("Error fetching Airtable records:", response.text)
        return {}

def add_job_to_airtable(job):
    """Adds a new job posting to Airtable."""
    data = {"fields": job}
    response = requests.post(AIRTABLE_URL, headers=HEADERS, data=json.dumps(data))
    if response.status_code in [200, 201]:
        print("Added job:", job["Job Title"])
    else:
        print("Failed to add job:", job["Job Title"], response.text)

def delete_job_from_airtable(record_id, job):
    """Deletes a job posting from Airtable using its record ID."""
    delete_url = f"{AIRTABLE_URL}/{record_id}"
    response = requests.delete(delete_url, headers=HEADERS)
    if response.status_code == 200:
        print("Deleted job:", job["Job Title"])
    else:
        print("Failed to delete job:", job["Job Title"], response.text)

def update_airtable():
    """Main function to update Airtable:
       - Scrapes job postings for all companies defined in companies.json.
       - Compares scraped jobs with existing Airtable records.
       - Adds new jobs and deletes jobs that are no longer found.
    """
    new_jobs = []
    for company_conf in companies:
        new_jobs.extend(scrape_company(company_conf))
    
    # Create a dictionary of scraped jobs keyed by a unique identifier.
    scraped_jobs = {}
    for job in new_jobs:
        key = f"{job['Company']}|{job['Job Title']}|{job['Apply URL']}"
        scraped_jobs[key] = job

    airtable_jobs = get_airtable_jobs()

    # Add any new job that is not already in Airtable.
    for key, job in scraped_jobs.items():
        if key not in airtable_jobs:
            add_job_to_airtable(job)
        else:
            # Optionally update existing records if needed.
            pass

    # Delete jobs from Airtable that are no longer scraped.
    for key, record_id in airtable_jobs.items():
        if key not in scraped_jobs:
            delete_job_from_airtable(record_id, {"Job Title": key.split("|")[1]})

# Main script execution.
if __name__ == "__main__":
    update_airtable()
