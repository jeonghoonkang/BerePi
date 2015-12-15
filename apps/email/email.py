# Try running this locally.
def send_simple_message():
    return requests.post(
        "https://api.mailgun.net/v3/samples.mailgun.org/messages",
        auth=("api", "key-3ax6xnjp29jd6fds4gc373sgvjxteol0"),
        data={"from": "Excited User <excited@samples.mailgun.org>",
              "to": ["devs@mailgun.net"],
              "subject": "Hello",
              "text": "Testing some Mailgun awesomeness!"})
