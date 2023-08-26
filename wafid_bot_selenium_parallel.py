# Import packages
import asyncio
import logging
import os
import random
import re
import time
import warnings
from datetime import datetime

# If you get an error with the ChromeBrowser version, pip install chromedriver-binary and chromedriver-binary-auto from https://pypi.org/project/chromedriver-binary/
# Then run pip install --upgrade --force-reinstall chromedriver-binary-auto
# This will install redetect the required version and install the newest suitable chromedriver
# There is no need to use service=Service(executable_path=ChromeDriverManager().install()) anymore
import chromedriver_binary  # This will add the executable to your PATH so it will be found. You can also get the absolute filename of the binary with chromedriver_binary.chromedriver_filename
import gspread
import numpy as np
import pandas as pd
import pytz
from bs4 import BeautifulSoup
from capmonstercloudclient import CapMonsterClient, ClientOptions
from capmonstercloudclient.requests import RecaptchaV3ProxylessRequest
from dotenv import load_dotenv
from joblib import Parallel, delayed
from oauth2client.service_account import ServiceAccountCredentials
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from seleniumwire import webdriver
from telegram import Bot
from telegram.constants import ParseMode

warnings.filterwarnings(action="ignore")

# Load environment variables
load_dotenv()

# Extension path for the Captcha Solving service (Cap Monster)
path = os.path.dirname(os.path.expanduser("~") + "/cap_monster_extension/manifest.json")

# Set the Chrome options (DO not disable images as this causes the captcha test to fail)
chrome_options = Options()
chrome_options.add_argument("start-maximized") # Required for a maximized Viewport
chrome_options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation', 'disable-popup-blocking']) # Disable pop-ups to speed up browsing
chrome_options.add_experimental_option("detach", True) # Keeps the Chrome window open after all the Selenium commands/operations are performed 
chrome_options.add_experimental_option('prefs', {'intl.accept_languages': 'en,en_US'}) # Operate Chrome using English as the main language
chrome_options.add_argument("--headless=new") # Operate Selenium in headless mode
chrome_options.add_argument('--no-sandbox') # Disables the sandbox for all process types that are normally sandboxed. Meant to be used as a browser-level switch for testing purposes only
chrome_options.add_argument('--disable-gpu') # An additional Selenium setting for headless to work properly, although for newer Selenium versions, it's not needed anymore
chrome_options.add_argument("enable-features=NetworkServiceInProcess") # Combats the renderer timeout problem
chrome_options.add_argument("disable-features=NetworkService") # Combats the renderer timeout problem
chrome_options.add_experimental_option('extensionLoadTimeout', 45000) # Fixes the problem of renderer timeout for a slow PC
chrome_options.add_argument("--window-size=1920x1080") # Set the Chrome window size to 1920 x 1080

# Global inputs (1): Basic information
base_url = "https://wafid.com/medical-status-search/"
slip_number_list_len = 100
parallel_jobs = -1
webdriver_waiting_time = 30
recaptcha_retries = 5

###-----------------------------###-----------------------------###

# Global inputs (2): Get the list of slip numbers from the Google Sheet --> https://docs.google.com/spreadsheets/d/1F2F2yWmvMebUG1rtppzt1Z9RZ9bOSHwu2VjXzk4XmC8/edit?pli=1#gid=0
# Replace 'your_spreadsheet_key' with the key of your Google Sheets document.
# You can find the key in the URL of your spreadsheet: 'https://docs.google.com/spreadsheets/d/your_spreadsheet_key/edit'
def google_sheet_reader():
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

    # Create a list of slip numbers from the provided slip number
    slip_numbers_list = []
    starting_slip_number = int(df_slip_numbers["slip_number"][0])
    for i in range(1, slip_number_list_len + 1):
        slip_numbers_list.append(starting_slip_number)
        starting_slip_number += 1
    
    # Return the slip_numbers_list and the starting slip number
    return slip_numbers_list, df_slip_numbers["slip_number"][0]

###-----------------------------###-----------------------------###

# Define a function to specify the proxy configuration
def chrome_proxy(user: str, password: str, endpoint: str):
    wire_options = {
        "proxy": {
            "http": f"http://{user}:{password}@{endpoint}",
            "https": f"http://{user}:{password}@{endpoint}",
        },
        "auto_config": False # Comment this out if you want to use proxies
    }

    return wire_options

###-----------------------------###-----------------------------###

def solve_capmonster_captcha(slip_number):
    """
    A function that solves the recaptcha V3 using the capmonster service
    """
    async def solve_captcha_async(num_requests):
        tasks = [asyncio.create_task(cap_monster_client.solve_captcha(recaptcha3request)) 
                for _ in range(num_requests)]
        return await asyncio.gather(*tasks, return_exceptions=True)

    key = os.getenv('CAPMONSTER_KEY')
    client_options = ClientOptions(api_key=key)
    cap_monster_client = CapMonsterClient(options=client_options)

    recaptcha3request = RecaptchaV3ProxylessRequest(
        websiteUrl="https://wafid.com/medical-status-search/",
        websiteKey="6LflPAwnAAAAAL2wBGi6tSyGUyj-xFvftINOR9xp",
        min_score=0.9
    )

    nums = 3

    # Async test
    async_responses = asyncio.run(solve_captcha_async(nums))
    captcha_response = async_responses[0]["gRecaptchaResponse"]
    logging.info(f"Captcha response of {slip_number}: {captcha_response}")
    return captcha_response

###-----------------------------###-----------------------------###

# Define a function to enter the GCC slip number and click on the "Check" button
def gcc_enter_slip_number_func(driver, slip_number, is_randomize_waiting_time):
    """
    A function to enter the GCC slip number and click on the "Check" button
    """
    # Solve the captcha
    captcha_response = solve_capmonster_captcha(slip_number=slip_number)
    
    # Inject the response in the InnerHTML of g-recaptcha-response
    driver.execute_script(f"document.getElementById('g-recaptcha-response').innerHTML='{captcha_response}'")

    # Do the actions you want to do on the page
    for idx in range(recaptcha_retries):
        # Declare a waiting time based on the iteration number
        if idx + 1 <= 5:
            wait_time = 5 # 5 seconds
        elif idx + 1 > 5 and idx + 1 <= 10:
            wait_time = 7.5 # 7.5 seconds
        else:
            wait_time = 10 # 10 seconds

        # Extract the captcha message. Don't use driver.find_element because it is slow
        soup1 = BeautifulSoup(markup=driver.page_source, features="html.parser")
        captcha_msg = soup1.select_one("input.g-recaptcha+p")
        gcc_field_content = soup1.select_one("input[placeholder='Enter GCC Slip Number']").get_attribute_list("value")[0]
        logging.info(f"captcha_msg of gcc_slipe_number_checker iteration {idx + 1} for slip number {slip_number}: {captcha_msg}")
        logging.info(f"gcc_field_content of gcc_slipe_number_checker iteration {idx + 1} for slip number {slip_number}: {gcc_field_content}")

        # If the captcha_msg is empty and gcc_field_content contains a number, this means that the form was submitted successfully and we can break out of the loop
        # Otherwise, we need to clear the field and try inputting the form number again
        if captcha_msg is None and gcc_field_content is not None:
            break
        else:
            # Clear the form, re-enter the slip number and re-submit the form
            driver.find_element(by=By.XPATH, value="//input[@id='id_gcc_slip_no']").clear()
            time.sleep(2.5)
            if is_randomize_waiting_time == True:
                for char in str(slip_number):
                    driver.find_element(by=By.XPATH, value="//input[@id='id_gcc_slip_no']").send_keys(char)
                    time.sleep(random.uniform(0.1, 0.2)) # Generate a random number between 0.1 and 0.2
            else:
                driver.find_element(by=By.XPATH, value="//input[@id='id_gcc_slip_no']").send_keys(slip_number)
            time.sleep(wait_time)

            # Submit the form (Clicking on the 'Check' button directly using this command does not always work --> driver.execute_script("document.getElementById('med-status-form-submit').click()"))
            # The instructions of solving the invisible captcha were taken from this link --> https://captchaforum.com/threads/how-to-automatically-solve-invisible-recaptcha-v2.2055/
            driver.execute_script("document.getElementsByClassName('ui form')[0].submit()")
    return idx, captcha_msg

# Define a function to extract the medical center and send a Telegram notification
def extract_medical_center_parallel(slip):
    """
    This is a function that extracts the medical center and sends a Telegram notification after the slip number has been successfully submitted.
    Parameters of the function:
    - driver: Chrome web driver
    - slip: Current slip number
    """
    # Instantiate the logger
    logging.basicConfig(
        level="INFO",
        filename="wafid_bot_logs.log",
        datefmt="%Y-%m-%d %H:%M:%S",
        format="%(levelname)s - %(asctime)s - %(message)s",
    )

    # Global inputs (3): Telegram bot
    wafid_bot_token = os.getenv("WAFID_BOT_TOKEN")
    wafid_chat_id = os.getenv("WAFID_BOT_CHAT_ID")
    errors_bot_token = os.getenv("ERRORS_BOT_TOKEN")
    errors_bot_chat_id = os.getenv("ERRORS_BOT_CHAT_ID")
    
    # Global inputs (4): Proxy credentials
    PROXY_SERVICE_USERNAME = os.getenv("PROXY_SERVICE_USERNAME")
    PROXY_SERVICE_PASSWORD = os.getenv("PROXY_SERVICE_PASSWORD")
    PROXY_SERVICE_ENDPOINT = os.getenv("PROXY_SERVICE_ENDPOINT")

    # Define an event loop to manage and execute async tasks such as coroutines and callbacks and assign it to the parallel process using set_event_loop 
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Create the bot objects
    wafid_bot_obj = Bot(token=wafid_bot_token)
    bot_errors = Bot(token=errors_bot_token)

    # Function to send Telegram message
    async def send_telegram_message(bot, chat_id, message):
        await bot.send_message(chat_id=chat_id, text=message, parse_mode=ParseMode.MARKDOWN)

    try:
        # Instantiate the web driver and set the implicit waiting time to be 60 seconds
        proxies = chrome_proxy(PROXY_SERVICE_USERNAME, PROXY_SERVICE_PASSWORD, PROXY_SERVICE_ENDPOINT)
        driver = webdriver.Chrome(options=chrome_options, seleniumwire_options=proxies)
        driver.implicitly_wait(60)

        # Navigate to ip.oxylabs.io to get the IP address
        driver.get("https://ip.oxylabs.io/")
        logging.info(f'\nYour IP is: {re.search(r"[0-9].{2,}", driver.page_source).group()}')
        
        # Navigate to the website
        driver.get(base_url)

        # Wait for the "Wafid Slip Number" radio button and click on it
        WebDriverWait(driver, webdriver_waiting_time).until(EC.element_to_be_clickable((By.XPATH, "//input[@id='id_search_variant_1']")))
        driver.execute_script("document.getElementById('id_search_variant_1').click()")

        # Wait until the "GCC Slip NO" selector appears
        WebDriverWait(driver, webdriver_waiting_time).until(EC.presence_of_element_located((By.XPATH, "//input[@id='id_gcc_slip_no']")))

        # Extract the HTML source code of the page with BeautifulSoup
        soup2 = BeautifulSoup(markup=driver.page_source, features="html.parser")

        # Extract the status message. It could be one of three options.
        # Option 1 (Pass - The traveled_country_name and medical center can be extracted): Selector --> input[name='traveled_country__name']
        # Option 2 (Pass - Records not found): Selector --> div.header
        # Option 3 (Fail - revert back to captcha on the previous page): Selector --> input.g-recaptcha+p
        status_message = soup2.select_one(selector="input[name='traveled_country__name'], div.header, input.g-recaptcha+p")
        logging.info(f"status_message for slip number {slip}: {status_message}")

        # Invoke the "gcc_enter_slip_number_func" function
        idx, captcha_msg = gcc_enter_slip_number_func(driver=driver, slip_number=slip, is_randomize_waiting_time=True)

        # If it is the last iteration and and the form was not submitted successfuly, send a message to Telegram saying that it was not possible to submit the form for this slip number
        if idx + 1 == recaptcha_retries and captcha_msg is not None:
            loop.run_until_complete(send_telegram_message(
                bot=wafid_bot_obj,
                chat_id=wafid_chat_id,
                message=f"It was not possible to submit the form successfully for slip number {slip} after {idx + 1} times"
            ))
        
        # Download the HTML content of the page and extract the status message again
        soup3 = BeautifulSoup(markup=driver.page_source, features="html.parser")
        status_message2 = soup3.select_one(selector="input[name='traveled_country__name'], div.header, input.g-recaptcha+p")
        
        # The result could either be "Records not found" pr "Medical Center found". Either way, send a Telegram message
        if status_message2.get_text(strip=True) == "Records not found":
            records_not_found_message = f"No records found for slip number {slip}. It took {idx + 1} iterations to submit the form successfully"

            # Print a message saying that there was no record found for this slip number
            logging.info(records_not_found_message)

            # Send a Telegram message saying that there was no record found for this slip number
            loop.run_until_complete(send_telegram_message(bot=wafid_bot_obj, chat_id=wafid_chat_id, message=records_not_found_message))
        if status_message2.get_attribute_list("value")[0] is not None:
            # Extract the fields of interest
            output_dict = {
                "slip_number": slip,
                "country": soup3.select_one(selector="input[name='traveled_country__name']").get_attribute_list("value")[0],
                "medical_center": soup3.select_one(selector="input[name='medical_center']").get_attribute_list("value")[0]
            }

            # Print the output
            logging.info(output_dict)

            # Send a Telegram message saying that a record for that slip number was found
            if output_dict["country"] == "Saudi Arabia":
                output_dict_message = f"Records were found for slip number {slip}. It took {idx + 1} iterations to submit the form successfully. Info --> *{output_dict}*" # Bold the output
            else:
                output_dict_message = f"Records were found for slip number {slip}. It took {idx + 1} iterations to submit the form successfully. Info --> {output_dict}" # Normal text
            loop.run_until_complete(send_telegram_message(
                bot=wafid_bot_obj,
                chat_id=wafid_chat_id,
                message=output_dict_message
            ))
        
        # Close the driver to save memory
        driver.quit()
    except Exception as e:
        # Quit the driver to not take up memory
        driver.quit()

        # Send a message to the Telegram bot saying that an error occurred
        logging.exception(f"An error occurred while crawling the wafid bot for slip number {slip}: {e}")
        loop.run_until_complete(send_telegram_message(bot=bot_errors, chat_id=errors_bot_chat_id, message=f"An error occurred while crawling the wafid bot: {e}"))

def execute_all():
    """
    A function to execute the functions defined above
    """
    # Execute the google_sheet_reader function to get the slip number list
    slip_numbers_list = google_sheet_reader()[0]
    Parallel(n_jobs=parallel_jobs, verbose=13)(delayed(extract_medical_center_parallel)(slip=slip) for slip in slip_numbers_list)

if __name__ == "__main__":
    while True:
        # Get the current time in Dhaka
        tz_Dhaka = pytz.timezone('Asia/Dhaka')
        datetime_Dhaka = int(datetime.now(tz_Dhaka).strftime("%H"))
        if datetime_Dhaka >= 10 and datetime_Dhaka <= 22:
            # Execute the google_sheet_reader function to get the starting slip number
            starting_slip_number = google_sheet_reader()[1]

            # Execute the crawling
            execute_all()
        else:
            # Don't do anything
            pass
