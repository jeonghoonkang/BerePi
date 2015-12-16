import requests
# Try running this locally.
def send_email():
  return requests.post(
    "https://api.mailgun.net/v3/sandboxc1aa4e92f05144a3973f6f8c031849e3.mailgun.org",
    auth=("api", "key-3fb9acb996e674af4816edf1055a72f7"),
    data={"from": "TinyOS DEV <kang@keti>",
    "to": ["gadin.kang@gmail.com"],
    "subject": "Sensor mail running",
    "text": "Merry Christmas !"})

if __name__ == "__main__" :
    send_email()
