from together import Together
import os

def ask_llm(prompt: str) -> str:
    try:
        client = Together(api_key=os.getenv("TOGETHER_API_KEY"))
        response = client.chat.completions.create(
            model="deepseek-ai/DeepSeek-V3",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=2048
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"❌ Erreur LLM: {str(e)}")
        return ""
