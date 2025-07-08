import requests

class DoorDashScraper:
    def __init__(self, url):
        self.url = url
        self.session = requests.Session()
        self.auth_token = None


    def get_auth_token(self):
        auth_url = "https://devconsole.doordash.team/api/auth/doordash/refresh"
        resp = self.session.get(auth_url)
        print("Auth response:", resp.text)  # Add this line
        resp.raise_for_status()
        self.auth_token = resp.json().get("token")
        if not self.auth_token:
            raise Exception("Auth token not found in response")



    def scrape(self):
        if not self.auth_token:
            self.get_auth_token()
        headers = {"Authorization": f"Bearer {self.auth_token}"}
        resp = self.session.get(self.url, headers=headers)
        resp.raise_for_status()
        return resp.text  # Or parse a