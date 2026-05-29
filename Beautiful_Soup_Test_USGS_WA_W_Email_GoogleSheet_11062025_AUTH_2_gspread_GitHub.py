import gspread
from google.oauth2.service_account import Credentials  # Google Sheets
from google.oauth2.credentials import Credentials as GmailCredentials  # Gmail OAuth
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import time

# Selenium imports
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# -----------------------------
# CONFIGURATION (USER MUST FILL IN)
# -----------------------------

# Path to your Google Sheets service account JSON
SERVICE_ACCOUNT_FILE = "PATH/TO/YOUR/service_account.json"  
# (Never commit the real file to GitHub)

# Google Sheet ID (safe to share publicly if the sheet itself is private)
SPREADSHEET_ID = "YOUR_SPREADSHEET_ID_HERE"

# Gmail OAuth client secret file
GMAIL_CLIENT_SECRET = "PATH/TO/YOUR/gmail_client_secret.json"
# (Never commit the real file to GitHub)

# Where Gmail OAuth tokens will be stored locally
TOKEN_PATH = "token.json"  # Safe to commit if empty; not safe if it contains tokens

SENDER_EMAIL = "YOUR_EMAIL@gmail.com"  # You may leave this blank for users to fill in
EMAIL_SUBJECT = "Current Washington River Levels"

# -----------------------------
# SETUP SELENIUM
# -----------------------------
chrome_options = Options()
chrome_options.add_argument("--ignore-ssl-errors=true")

driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=chrome_options
)

# -----------------------------
# GOOGLE SHEETS AUTH
# -----------------------------
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

creds = Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=SCOPES
)

client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).get_worksheet(0)

# -----------------------------
# GMAIL AUTH
# -----------------------------
GMAIL_SCOPES = ['https://www.googleapis.com/auth/gmail.send']

if os.path.exists(TOKEN_PATH):
    gmail_creds = GmailCredentials.from_authorized_user_file(TOKEN_PATH, GMAIL_SCOPES)
else:
    flow = InstalledAppFlow.from_client_secrets_file(GMAIL_CLIENT_SECRET, GMAIL_SCOPES)
    gmail_creds = flow.run_local_server(port=0)
    with open(TOKEN_PATH, 'w') as token_file:
        token_file.write(gmail_creds.to_json())

gmail_service = build('gmail', 'v1', credentials=gmail_creds)

# -----------------------------
# SCRAPE USGS PAGE
# -----------------------------
url = "https://waterdata.usgs.gov/state/washington/#groupBy=county&sortOrder=name-ascending"
driver.get(url)

WebDriverWait(driver, 30).until(
    EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'data-type-row-container')]"))
)

def get_gauge_data(gauge_number):
    links = driver.find_elements(By.XPATH, "//a[@class='usa-link']")
    for link in links:
        href = link.get_attribute('href')
        if str(gauge_number) in href:
            parent = link.find_element(By.XPATH, "ancestor::div[@class='location-details-container']")
            gauge_name = parent.find_element(By.XPATH, ".//div[@class='grid-col-fill']").text
            date_time = parent.find_element(By.XPATH, ".//div[@role='gridcell'][@class='latest-time-column']").text.strip()
            flow_level = parent.find_element(By.XPATH, ".//span[@role='note']").text
            return href, gauge_name, date_time, flow_level
    return None

# -----------------------------
# PROCESS GOOGLE SHEET
# -----------------------------
all_rows = sheet.get_all_values()
primary_keys = all_rows[1]  # Row 2
recipient_rows = all_rows[2:]  # Row 3+

for row in recipient_rows:
    recipient_email = row[2]

    if recipient_email:
        message = "Current Washington River Levels:<br><br>"
        interested = []

        for col_index in range(3, len(row)):
            if row[col_index] == 'TRUE':
                interested.append(primary_keys[col_index])

        for river in interested:
            data = get_gauge_data(river)
            if data:
                href, name, dt, flow = data
                message += f'<a href="{href}">USGS Gauge {river}</a><br>'
                message += f"Gauge Name: {name}<br>"
                message += f"Date/Time: {dt}<br>"
                message += f"Flow Level: {flow}<br><br>"

        msg = MIMEMultipart('mixed')
        msg['To'] = recipient_email
        msg['From'] = SENDER_EMAIL
        msg['Subject'] = EMAIL_SUBJECT
        msg.attach(MIMEText(message, 'html'))

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        gmail_message = {'raw': raw}

        try:
            gmail_service.users().messages().send(userId="me", body=gmail_message).execute()
            print(f"Email sent to {recipient_email}")
        except Exception as e:
            print(f"Failed to send email to {recipient_email}: {e}")

driver.quit()



                


