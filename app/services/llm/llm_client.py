import requests
from app.core.config import settings


class MinimaxClient:

    def __init__(self):
        if not settings.minmax_api_key:
            raise ValueError("MINIMAX_API_KEY not set")

        self.base_url = "https://api.minimax.chat/v1/text/chatcompletion_v2"
        self.api_key = settings.minmax_api_key

    def generate_analysis(self, prompt: str) -> str:

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "abab6.5-chat",  # change if needed
            "messages": [
                {"role": "system", "content": "You are an e-commerce approval assistant."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
        }

        response = requests.post(self.base_url, headers=headers, json=payload)

        if response.status_code != 200:
            raise Exception(f"Minimax Error: {response.text}")

        data = response.json()
        print(data)
        return data["reply"]