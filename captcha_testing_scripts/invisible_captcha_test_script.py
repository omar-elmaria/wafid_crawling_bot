import sys
import os
from dotenv import load_dotenv

load_dotenv()

from twocaptcha import TwoCaptcha

api_key = os.getenv("TWO_CAPTCHA_KEY")

solver = TwoCaptcha(api_key)

try:
    result = solver.recaptcha(
        sitekey='6LdO5_IbAAAAAAeVBL9TClS19NUTt5wswEb3Q7C5',
        url='https://2captcha.com/demo/recaptcha-v2-invisible',
        invisible=1)

except Exception as e:
    sys.exit(e)

else:
    sys.exit('solved: ' + str(result))