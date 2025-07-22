from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from assistant import SQLAssistant
from pydantic import BaseModel

app = FastAPI()

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

assistant = SQLAssistant()

class QueryRequest(BaseModel):
    question: str

@app.post("/query")
async def process_query(request: QueryRequest):
    try:
        sql_query, response = assistant.ask_question(request.question)
        return {
            "sql_query": sql_query,
            "response": response
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)