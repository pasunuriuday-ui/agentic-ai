print("START")

from app.services.llm_service import LLMService

llm = LLMService()

print("MODEL READY")

response = llm.generate("AI is")

print("OUTPUT:\n")
print(response)