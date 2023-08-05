import os
import time

from dotenv import load_dotenv
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from twocaptcha import TwoCaptcha
from selenium.common.exceptions import JavascriptException
import string

import warnings

warnings.filterwarnings(action="ignore")

# Load environment variables
load_dotenv()

# Define the timestamp showing the start of the script
t1 = time.time()

# Set the Chrome options
chrome_options = Options()
chrome_options.add_argument("start-maximized") # Required for a maximized Viewport
chrome_options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation', 'disable-popup-blocking']) # Disable pop-ups to speed up browsing
chrome_options.add_experimental_option("detach", True) # Keeps the Chrome window open after all the Selenium commands/operations are performed 
chrome_options.add_experimental_option('prefs', {'intl.accept_languages': 'en,en_US'}) # Operate Chrome using English as the main language
# chrome_options.add_argument('--blink-settings=imagesEnabled=false') # Disable images
# chrome_options.add_argument('--disable-extensions') # Disable extensions
# chrome_options.add_argument("--headless=new") # Operate Selenium in headless mode
chrome_options.add_argument('--no-sandbox') # Disables the sandbox for all process types that are normally sandboxed. Meant to be used as a browser-level switch for testing purposes only
chrome_options.add_argument('--disable-gpu') # An additional Selenium setting for headless to work properly, although for newer Selenium versions, it's not needed anymore
chrome_options.add_argument("enable-features=NetworkServiceInProcess") # Combats the renderer timeout problem
chrome_options.add_argument("disable-features=NetworkService") # Combats the renderer timeout problem
chrome_options.add_experimental_option('extensionLoadTimeout', 45000) # Fixes the problem of renderer timeout for a slow PC
chrome_options.add_argument("--window-size=1920x1080") # Set the Chrome window size to 1920 x 1080

# Global inputs (1): Basic information
base_url = "https://wafid.com/medical-status-search/"

# Global inputs (2): Captcha
solver = TwoCaptcha(os.getenv("TWO_CAPTCHA_KEY"))
sitekey = "6LflPAwnAAAAAL2wBGi6tSyGUyj-xFvftINOR9xp"

# Global inputs (3): List of slip numbers
slip_numbers = ["90907202359893415", "90907202359893394", "90907202359893395", "90907202359893396", "90907202359893397", "90907202359893398"]

# Helper functions
def solve_captcha(sitekey, url):
    try:
        result = solver.recaptcha(sitekey=sitekey, url=url, invisible=1)
        captcha_key = result.get('code')
        print(f"Captcha solved. The key is: {captcha_key}")
    except Exception as err:
        print(err)
        print(f"Captcha not solved...")
        captcha_key = None

    return captcha_key

def invoke_callback_function(driver, captcha_key):
    # Invoke the captcha token in the inner HTML of the g-recaptcha-response element. This part is not necessary for this specific website
    driver.execute_script(f'document.getElementById("g-recaptcha-response").innerHTML="{captcha_key}"')
    driver.execute_script(f'document.getElementById("g-recaptcha-response-100000").innerHTML="{captcha_key}"')

    # Invoke the callback function
    driver.execute_script(f"window[___grecaptcha_cfg.clients[100000].P.P.callback]('TOKEN')")
    driver.execute_script(f"___grecaptcha_cfg.clients['100000']['P']['P']['promise-callback']('{captcha_key}')")

# Instantiate the web driver and set the implicit waiting time to be 60 seconds
driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)
driver.implicitly_wait(60)

# Navigate to the website
driver.get(base_url)

# Click on the "Wafid Slip Number" radio button
driver.find_element(by=By.XPATH, value="//input[@id='id_search_variant_1']").click()

# Wait until the "GCC Slip NO" selector appears and enter the first slip number
WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//input[@id='id_gcc_slip_no']")))
driver.find_element(by=By.XPATH, value="//input[@id='id_gcc_slip_no']").send_keys(slip_numbers[0])

# Solve the captcha (retry up to 3 times if it fails)
for i in range(3):
    print(f"Solving the captcha")
    captcha_token = solve_captcha(sitekey=sitekey, url=base_url)
    if captcha_token is not None:
        break

# Invoke the callback function
print(f"Invoking callback function")
invoke_callback_function(driver=driver, captcha_key=captcha_token)

# Click on the check button
driver.find_element(by=By.XPATH, value="//button[@id='med-status-form-submit']").click()

# Wait for the program
time.sleep(1000)

# Quit the web driver to save memory
driver.quit()