import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

import os
import json

import logging
import sys
from pytz import timezone

# --- CONFIGURATION ---
RESULTS_FILE = "found_results.json"  # Local file in the script's directory
SUBJECT_FILE = "subject.txt" # New file for the subject
BODY_FILE = "body.txt"      # New file for the clean email body
BUCHAREST_TZ = timezone('Europe/Bucharest')
# --- END CONFIGURATION ---

# Configure logging
# We'll rely on the shell to handle the main log file (log.txt) by piping STDOUT/STDERR.
# The logger will print to STDOUT, which is captured by 'tee output.txt'.
logging.basicConfig(level=logging.INFO, format='[%(asctime)s][%(levelname)s]: %(message)s', handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

# URL of the main page with dynamic year
base_url = "https://www.primaria-iasi.ro"
url = f"{base_url}/dm_iasi/portal.nsf/pagini/licitatii+2026-000465A2?Open"

# Search terms
search_terms = [
    ("Nr. 33", "964B"),
    ("Tudor Neculai", "971B"),
    ("Tudor Neculai", "971A"),
]

def parse_date(date_str):
    """Convert DD.MM.YYYY string to datetime object"""
    try:
        return datetime.strptime(date_str, '%d.%m.%Y')
    except ValueError:
        return None

def load_sent_results():
    """Load previously sent results from file"""
    try:
        if os.path.exists(RESULTS_FILE):
            with open(RESULTS_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Error loading sent results: {e}")
        return {}

def save_results(sent_results):
    """Save results to file"""
    try:
        with open(RESULTS_FILE, 'w') as f:
            json.dump(sent_results, f)
    except Exception as e:
        logger.error(f"Error saving sent results: {e}")

def format_results_as_html(recent_new_results):
    """
    Formats the recent new auction results as HTML, writes subject/body files, 
    and returns True if results were formatted, False otherwise.
    """
    if not recent_new_results:
        return False

    # 1. Prepare Subject Content
    all_matched_terms = set()
    for r in recent_new_results:
        all_matched_terms.update(r['matched_terms'])

    subject_content = f"[{', '.join(sorted(all_matched_terms))}]"
    write_file_output(SUBJECT_FILE, subject_content)

    # 2. Prepare HTML Body Content
    body_content = f"<h4>Found {len(recent_new_results)} recent new matching auctions:</h4>"
    body_content += "<hr>"

    for result in recent_new_results:
        body_content += "<div>"
        # Title
        body_content += f"<p><strong>Title:</strong> {result['title']}</p>"

        # PDF Link
        body_content += f'<p><strong>PDF URL:</strong> <a href="{result["pdf_url"]}">View Auction PDF</a></p>'

        # Date
        body_content += f"<p><strong>Date:</strong> {result['date_str']}</p>"

        # Matched terms list
        matched_terms_list = ', '.join(result['matched_terms'])
        body_content += f"<p><strong>Matched combinations:</strong> {matched_terms_list}</p>"

        body_content += "<hr>"
        body_content += "</div>"

    write_file_output(BODY_FILE, body_content)

    # Print the clean body content to STDOUT (for logging visibility in output.txt)
    logger.info(f"HTML Body Summary:\n{body_content[:200]}...")

    # Mark as sent and save results
    timestamp = datetime.now(BUCHAREST_TZ).strftime('%d.%m.%Y %H:%M:%S')
    old_results = load_sent_results()
    for result in recent_new_results:
        old_results[result['pdf_url']] = { 'title': result['title'], 'date': result['date_str'], 'sent_at': timestamp }
    save_results(old_results)

    return True

def write_file_output(filename, content):
    """Write content to a file for GitHub Actions to read."""
    try:
        with open(filename, 'w') as f:
            f.write(content)
    except Exception as e:
        logger.error(f"Failed to write file {filename}: {e}")
        sys.exit(1)

def scrape_parking_auctions(search_terms):
    old_results = load_sent_results()
    two_weeks_ago = datetime.now() - timedelta(days=14)

    try:
        headers = { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36' }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        if not (table := soup.find('table', id='fisierePMI')):
            logger.warning("Table with id 'fisierePMI' not found")
            return

        results = []
        for row in table.find('tbody').find_all('tr') if table.find('tbody') else table.find_all('tr'):
            columns = row.find_all('td')
            if len(columns) >= 2:
                title_col = columns[0]
                link = title_col.find('a')
                title = link.text.strip() if link else title_col.text.strip()
                pdf_url = link['href'] if link else None
                date_str = columns[1].text.strip()
                date = parse_date(date_str)
                title_lower = title.lower()

                matching_combos = []
                for term1, term2 in search_terms:
                    term1_lower = term1.lower()
                    term2_lower = term2.lower()

                    # Check if BOTH terms in the tuple are present in the title
                    if term1_lower in title_lower and term2_lower in title_lower:
                        matching_combos.append(f"('{term1}', '{term2}')")

                # If any combination matched, process the result
                if matching_combos:
                    full_pdf_url = f"{base_url}{pdf_url}"
                    results.append({ 'title': title, 'pdf_url': full_pdf_url, 'date_str': date_str, 'date': date, 'matched_terms': matching_combos })

        results.sort(key=lambda x: x['date'] if x['date'] else datetime.min, reverse=True)

        # Filter out already sent results
        new_results = [result for result in results if result['pdf_url'] not in old_results]

        # Check for recent new results
        if (recent_new_results := [r for r in new_results if r['date'] and r['date'] >= two_weeks_ago]):
            if format_results_as_html(recent_new_results):
                logger.info(f"Successfully finished. Found {len(recent_new_results)} new results.")
        else:
            # Note: We display the combinations in the log, not just single terms
            search_combo_strings = [f"('{t1}', '{t2}')" for t1, t2 in search_terms]
            logger.info(f"No recent new auctions (≤14 days) found matching combinations: {', '.join(search_combo_strings)}")

    except requests.RequestException as e:
        logger.error(f"Error fetching the webpage: {e}")
        sys.exit(1) # Exit with error code
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        sys.exit(1) # Exit with error code


def main():
    logger.info("*** PARKING AUCTION MONITOR ***")

    logger.info("Starting parking auction monitor...")
    logger.info(f"Monitoring URL: {url}")
    search_combo_strings = [str(combo) for combo in search_terms]
    logger.info(f"Search terms: {', '.join(search_combo_strings)}")

    try:
        scrape_parking_auctions(search_terms)
        return 0
    except KeyboardInterrupt:
        logger.info("\nScript stopped by user")
        return 0
    except Exception as e:
        # Logging will handle the exception details
        return 1

if __name__ == "__main__":
    sys.exit(main())
