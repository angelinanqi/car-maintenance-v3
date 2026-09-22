import os
from dotenv import load_dotenv
from ollama import chat

load_dotenv()


class OllamaClient:
    def __init__(self):
        model = os.getenv("OLLAMA_MODEL")

        if not model:
            raise ValueError("OLLAMA_MODEL is not set in the .env file.")

        self.model: str = model

    def generate(self, prompt: str, *, schema: dict | None = None) -> str:
        if not prompt.strip():
            raise ValueError("Prompt cannot be empty.")

        messages = [
            {
                "role": "user",
                "content": prompt,
            }
        ]

        if schema is None:
            response = chat(model=self.model, messages=messages)
        else:
            response = chat(
                model=self.model,
                format=schema,
                messages=messages,
            )

        content = response.message.content

        if content is None:
            raise ValueError("Ollama returned an empty response.")

        return content
