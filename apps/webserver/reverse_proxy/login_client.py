import argparse
import requests


def main():
    parser = argparse.ArgumentParser(description="Example script to login to the status server")
    parser.add_argument("--base-url", default="http://localhost:9000", help="base URL of the status server")
    parser.add_argument("--username", default="admin", help="login username")
    parser.add_argument("--password", default="secret", help="login password")
    args = parser.parse_args()

    session = requests.Session()
    login_url = f"{args.base_url}/"
    login_data = {
        "username": args.username,
        "password": args.password,
    }

    print(f"[1] POST to {login_url}")
    response = session.post(login_url, data=login_data)
    print("[2] status:", response.status_code)
    print("[3] response:\n", response.text)


if __name__ == "__main__":
    main()
