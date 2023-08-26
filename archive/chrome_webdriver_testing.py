from selenium.webdriver.chrome.options import Options
from seleniumwire import webdriver
import time
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import os
from dotenv import load_dotenv
import chromedriver_binary

load_dotenv()


# Set the Chrome options
chrome_options = Options()
chrome_options.add_argument("start-maximized") # Required for a maximized Viewport
chrome_options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation', 'disable-popup-blocking']) # Disable pop-ups to speed up browsing
chrome_options.add_experimental_option("detach", True) # Keeps the Chrome window open after all the Selenium commands/operations are performed
chrome_options.add_experimental_option('prefs', {'intl.accept_languages': 'en,en_US'}) # Operate Chrome using English as the main language
chrome_options.add_argument('--blink-settings=imagesEnabled=false') # Disable images
chrome_options.add_argument('--disable-extensions') # Disable extensions
# chrome_options.add_argument("--headless=new") # Operate Selenium in headless mode
chrome_options.add_argument('--no-sandbox') # Disables the sandbox for all process types that are normally sandboxed. Meant to be used as a browser-level switch for testing purposes only
chrome_options.add_argument('--disable-gpu') # An additional Selenium setting for headless to work properly, although for newer Selenium versions, it's not needed anymore
chrome_options.add_argument("enable-features=NetworkServiceInProcess") # Combats the renderer timeout problem
chrome_options.add_argument("disable-features=NetworkService") # Combats the renderer timeout problem
chrome_options.add_experimental_option('extensionLoadTimeout', 45000) # Fixes the problem of renderer timeout for a slow PC
chrome_options.add_argument("--window-size=1920x1080") # Set the Chrome window size to 1920 x 1080
print(chromedriver_binary.chromedriver_filename)

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

PROXY_SERVICE_USERNAME = os.getenv("PROXY_SERVICE_USERNAME")
PROXY_SERVICE_PASSWORD = os.getenv("PROXY_SERVICE_PASSWORD")
PROXY_SERVICE_ENDPOINT = os.getenv("PROXY_SERVICE_ENDPOINT")

proxies = chrome_proxy(PROXY_SERVICE_USERNAME, PROXY_SERVICE_PASSWORD, PROXY_SERVICE_ENDPOINT)

# Global inputs (1): Captcha
driver = webdriver.Chrome(service=Service(executable_path=ChromeDriverManager().install()), options=chrome_options, seleniumwire_options=proxies)
driver.get("https://www.google.com")
time.sleep(10)
print(driver.title)
driver.quit()