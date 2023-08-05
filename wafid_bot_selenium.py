import asyncio
import os
import time
import warnings

import gspread
import pandas as pd
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from telegram import Bot
from webdriver_manager.chrome import ChromeDriverManager

warnings.filterwarnings(action="ignore")

# Load environment variables
load_dotenv()

# Extension path for the Captcha Solving service (Cap Monster)
path = os.path.dirname(os.path.expanduser("~") + "\cap_monster_extension\manifest.json")

# Set the Chrome options
chrome_options = Options()
chrome_options.add_argument("start-maximized") # Required for a maximized Viewport
chrome_options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation', 'disable-popup-blocking']) # Disable pop-ups to speed up browsing
chrome_options.add_experimental_option("detach", True) # Keeps the Chrome window open after all the Selenium commands/operations are performed 
chrome_options.add_experimental_option('prefs', {'intl.accept_languages': 'en,en_US'}) # Operate Chrome using English as the main language
# chrome_options.add_argument("--headless=new") # Operate Selenium in headless mode
chrome_options.add_argument('--no-sandbox') # Disables the sandbox for all process types that are normally sandboxed. Meant to be used as a browser-level switch for testing purposes only
chrome_options.add_argument('--disable-gpu') # An additional Selenium setting for headless to work properly, although for newer Selenium versions, it's not needed anymore
chrome_options.add_argument("enable-features=NetworkServiceInProcess") # Combats the renderer timeout problem
chrome_options.add_argument("disable-features=NetworkService") # Combats the renderer timeout problem
chrome_options.add_experimental_option('extensionLoadTimeout', 45000) # Fixes the problem of renderer timeout for a slow PC
chrome_options.add_argument("--window-size=1920x1080") # Set the Chrome window size to 1920 x 1080

# Global inputs (1): Basic information
base_url = "https://wafid.com/medical-status-search/"
slip_number_list_len = 10

# Global inputs (2): Get the list of slip numbers from the Google Sheet --> https://docs.google.com/spreadsheets/d/1F2F2yWmvMebUG1rtppzt1Z9RZ9bOSHwu2VjXzk4XmC8/edit?pli=1#gid=0

# Replace 'your_spreadsheet_key' with the key of your Google Sheets document.
# You can find the key in the URL of your spreadsheet: 'https://docs.google.com/spreadsheets/d/your_spreadsheet_key/edit'
SPREADSHEET_KEY = '1F2F2yWmvMebUG1rtppzt1Z9RZ9bOSHwu2VjXzk4XmC8'
# Replace 'your_service_account.json' with the filename of your service account key.
SERVICE_ACCOUNT_FILE = os.path.expanduser("~") + "/service_account_key.json"

# Authenticate with Google Sheets API using the service account credentials
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, scope)
client = gspread.authorize(creds)

# Open the spreadsheet
spreadsheet = client.open_by_key(SPREADSHEET_KEY)

# Select the worksheet you want to read from (by index, starting from 0) or by title
worksheet = spreadsheet.get_worksheet(index=0)

# Get all values from the worksheet
df_slip_numbers = pd.DataFrame(worksheet.get_all_records(empty2zero=False, default_blank=None))

slip_numbers_list = []
starting_slip_number = int(df_slip_numbers["slip_number"][0])
for i in range(1, slip_number_list_len + 1):
    slip_numbers_list.append(starting_slip_number)
    starting_slip_number += 1

# Global inputs (3): Telegram bot
wafid_bot_token = os.getenv("WAFID_BOT_TOKEN")
wafid_chat_id = os.getenv("WAFID_BOT_CHAT_ID")
wafid_bot_obj = Bot(token=wafid_bot_token)

# Function to send Telegram message
async def send_telegram_message(bot, chat_id, message):
    await bot.send_message(chat_id=chat_id, text=message)

# Define the current event loop to manage and execute async tasks such as coroutines and callbacks
loop = asyncio.get_event_loop()

# Instantiate the web driver and set the implicit waiting time to be 60 seconds
driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)
driver.implicitly_wait(60)

# Navigate to the website
driver.get(base_url)

# Click on the "Wafid Slip Number" radio button
# driver.find_element(by=By.XPATH, value="//input[@id='id_search_variant_1']").click()
driver.execute_script("document.getElementById('id_search_variant_1').click()")

# Wait until the "GCC Slip NO" selector appears and enter the first slip number
WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//input[@id='id_gcc_slip_no']")))

# Define a function to enter the GCC slip number and click on the "Check" button
def gcc_slip_number_checker(slip_number):
    for idx in range(15):
        # Declare a waiting time based on the iteration number
        if idx + 1 <= 5:
            wait_time = 1.5 # 1.5 seconds
        elif idx + 1 > 5 and idx + 1 <= 10:
            wait_time = 2.5 # 2.5 seconds
        else:
            wait_time = 5 # 5 seconds

        # Extract the captcha message. Don't use driver.find_element because it is slow
        soup1 = BeautifulSoup(markup=driver.page_source, features="html.parser")
        captcha_msg = soup1.select_one("input.g-recaptcha+p")
        gcc_field_content = soup1.select_one("input[placeholder='Enter GCC Slip Number']").get_attribute_list("value")[0]
        print(f"captcha_msg of gcc_slipe_number_checker iteration {idx + 1}: {captcha_msg}")
        print(f"gcc_field_content of gcc_slipe_number_checker iteration {idx + 1}: {gcc_field_content}")

        if captcha_msg is None and gcc_field_content is not None:
            break
        else:
            # Clear the form, re-enter the slip number and re-submit the form
            driver.find_element(by=By.XPATH, value="//input[@id='id_gcc_slip_no']").clear()
            time.sleep(wait_time)
            driver.find_element(by=By.XPATH, value="//input[@id='id_gcc_slip_no']").send_keys(slip_number)
            time.sleep(wait_time)

            # If the previous command does not produce an exception, this means that the captcha message appeared, so we need to click on the "Check" button again. Otherwise, break out of the loop
            driver.execute_script("document.getElementById('med-status-form-submit').click()")
    return

# If this message "Error verifying reCAPTCHA, please try again" pops up, then click on the check button again, up to five times
for idx, slip in enumerate(slip_numbers_list):
    # Extract the HTML source code of the page with BeautifulSoup
    soup2 = BeautifulSoup(markup=driver.page_source, features="html.parser")

    # Extract the status message. It could be one of three options.
    # Option 1 (Pass - The traveled_country_name and medical center can be extracted): Selector --> input[name='traveled_country__name']
    # Option 2 (Pass - Records not found): Selector --> div.header
    # Option 3 (Fail - revert back to captcha on the previous page): Selector --> input.g-recaptcha+p
    status_message = soup2.select_one(selector="input[name='traveled_country__name'], div.header, input.g-recaptcha+p")
    print(f"status_message: {status_message}")

    # Wait until the desired data appears
    gcc_slip_number_checker(slip_number=slip)
    
    soup3 = BeautifulSoup(markup=driver.page_source, features="html.parser")
    status_message2 = soup3.select_one(selector="input[name='traveled_country__name'], div.header, input.g-recaptcha+p")
    if status_message2.get_text(strip=True) == "Records not found":
        print(f"No records found for slip number {slip}")
        loop.run_until_complete(send_telegram_message(bot=wafid_bot_obj, chat_id=wafid_chat_id, message=f"No records found for slip number {slip}"))
    if status_message2.get_attribute_list("value")[0] is not None:
        # Extract the fields of interest
        output_dict = {
            "slip_number": slip,
            "country": soup3.select_one(selector="input[name='traveled_country__name']").get_attribute_list("value")[0],
            "medical_center": soup3.select_one(selector="input[name='medical_center']").get_attribute_list("value")[0]
        }
        print(output_dict)
        loop.run_until_complete(send_telegram_message(
            bot=wafid_bot_obj,
            chat_id=wafid_chat_id,
            message=f"Records were found for slip number {slip}. Info --> {output_dict}"
        ))

    if idx + 1 == len(slip_numbers_list):
        print("End of iterations. Breaking out of the loop")
        break
    else:
        # Clear the text field containing the slip number
        driver.find_element(by=By.XPATH, value="//input[@id='id_gcc_slip_no']").clear()

        # Wait 1 second before entering the slip number
        time.sleep(2.5)

        # Enter a the slip number after the current iteration
        driver.find_element(by=By.XPATH, value="//input[@id='id_gcc_slip_no']").send_keys(slip_numbers_list[idx + 1])

        # Wait for 2.5 seconds before clicking on check
        time.sleep(2.5)

        # Click on "Check"
        driver.execute_script("document.getElementById('med-status-form-submit').click()")

        # Wait until the check button becomes clickable
        WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, "//button[@id='med-status-form-submit']")))

# Quit the web driver to save memory
driver.quit()