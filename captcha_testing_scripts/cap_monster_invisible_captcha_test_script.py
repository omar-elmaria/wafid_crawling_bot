import os
import time
import asyncio
from dotenv import load_dotenv
load_dotenv()

from capmonstercloudclient import CapMonsterClient, ClientOptions
from capmonstercloudclient.requests import RecaptchaV3ProxylessRequest

async def solve_captcha_async(num_requests):
    tasks = [asyncio.create_task(cap_monster_client.solve_captcha(recaptcha3request)) 
             for _ in range(num_requests)]
    return await asyncio.gather(*tasks, return_exceptions=True)
    

if __name__ == '__main__':
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
    async_start = time.time()
    async_responses = asyncio.run(solve_captcha_async(nums))
    print(f'average execution time async {1/((time.time()-async_start)/nums):0.2f} ' \
          f'resp/sec\nsolution: {async_responses[0]["gRecaptchaResponse"]}')