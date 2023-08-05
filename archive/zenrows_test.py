# pip install zenrows
from zenrows import ZenRowsClient

client = ZenRowsClient("c84413998bc4297620396e96beca26a9090ed581")
url = "https://httpbin.io/anything"

response = client.get(url)

print(response.text)