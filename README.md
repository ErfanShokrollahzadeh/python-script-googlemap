# Google Maps Dentist Scraper

A Python web scraper using Playwright to extract dentist business information from Google Maps. The script searches for dentists in a specified city, scrolls through results to load all available businesses (up to 200), and extracts key business details.

## Features

- **Anti-Detection Measures**: Uses random user-agents, Istanbul geolocation, and stealth scripts to avoid blocking
- **Dynamic Scrolling**: Intelligently scrolls the Google Maps results sidebar to load all available businesses
- **Comprehensive Data Extraction**: Captures business name, phone number, website URL, rating, and review count
- **Append Mode CSV**: Results are appended to `leads.csv` (doesn't overwrite existing data)
- **Progress Tracking**: Shows real-time progress during execution
- **Error Handling**: Robust retry logic and graceful handling of missing data
- **Command-Line Flexibility**: Easy city selection via CLI argument

## Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Playwright Browser

```bash
playwright install chromium
```

## Usage

### Basic Usage (Default: Istanbul)

```bash
python3 scraper.py
```

### Search Different City

```bash
python3 scraper.py --city "New York"
python3 scraper.py --city "London"
python3 scraper.py --city "Paris"
```

### Help

```bash
python3 scraper.py --help
```

## Output

The script generates a CSV file `leads.csv` with the following columns:

| Column        | Description                           |
| ------------- | ------------------------------------- |
| Business Name | Name of the dental clinic/business    |
| Phone Number  | Phone number (empty if not available) |
| Website URL   | Website URL (empty if not available)  |
| Rating        | Business rating (e.g., "4.5")         |
| Review Count  | Number of reviews (e.g., "127")       |

### Example Output

```
Business Name,Phone Number,Website URL,Rating,Review Count
Dr. Smith Dental Clinic,+90 212 555 1234,https://example.com,4.5,127
Istanbul Dentist,,https://dentist.tr,4.8,89
Smile Dental Care,+90 212 555 9876,,4.2,45
```

## Script Behavior

### Execution Flow

1. **Startup**: Initializes headless Chromium browser with anti-detection configuration
2. **Search**: Navigates to Google Maps and searches for "Dentist in [City]"
3. **Loading**: Scrolls the results sidebar to load all available businesses (typically takes 5-10 minutes)
4. **Extraction**: Clicks on each business to extract detailed information
5. **Saving**: Appends results to `leads.csv`
6. **Completion**: Prints final count of scraped businesses

### Expected Progress Output

```
Starting Google Maps scraper...
Launching browser...
Searching for 'Dentist in Istanbul'...
Search complete, loading results...
Scrolling to load all results...
Loaded 10 results...
Loaded 20 results...
Loaded 30 results...
No new results found. Total loaded: 52

Extracting details from 52 businesses...
Extracted 10/52 businesses...
Extracted 20/52 businesses...
Extracted 30/52 businesses...
Extracted 52/52 businesses...

Saving to leads.csv...
✓ Successfully scraped 52 businesses!
✓ Data saved to leads.csv
```

## Requirements

- Python 3.8+
- Playwright 1.40.0+
- Internet connection
- macOS, Windows, or Linux

## Data Notes

- **Missing Fields**: If a business doesn't have a phone number or website, those fields are left empty
- **Append Mode**: Each run appends new rows to `leads.csv` (doesn't create duplicates automatically)
- **Maximum Results**: Scraper caps at 200 results per search to avoid rate limiting
- **Timeout**: Stops scrolling after 90 seconds if no new results are found

## Troubleshooting

### No Output Appears

Make sure Playwright is installed:

```bash
playwright install chromium
```

### Script Gets Blocked

If Google Maps blocks your requests:

- Wait a few minutes before running again
- Try searching a different city first
- The script has built-in retry logic that retries failed searches once

### CSV File Not Created

- Check that you have write permissions in the current directory
- The script must complete successfully (no interruption)
- Look for error messages in the terminal output

## Performance

- **Typical Runtime**: 5-15 minutes depending on number of results
- **Results Loaded**: 30-100+ businesses per search (varies by city)
- **Data Quality**: Empty fields are left blank (not N/A or "Unknown")

## Limitations

- Google Maps may rate-limit or block aggressive scraping
- Business data is current as of the scraping date
- Some businesses may not have all fields available (phone, website, reviews)
- Requires active internet connection
- Headless browser may behave differently than interactive browser

## License

Use responsibly and respect Google Maps terms of service and local laws.

## Support

For issues or improvements, check the script output for error messages and ensure:

1. Dependencies are installed (`requirements.txt`)
2. Playwright browser is installed (`playwright install chromium`)
3. You have a stable internet connection
4. You're not being rate-limited by Google Maps
