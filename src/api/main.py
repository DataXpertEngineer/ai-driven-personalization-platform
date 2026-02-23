"""FastAPI app: GET /recommendations/<user_id> hybrid retrieval."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.api.recommendations import get_recommendations_for_user
from src.utils.logger import logger

app = FastAPI(
    title="Personalization Recommendations API",
    description="Hybrid retrieval: vector (Milvus) + graph (Neo4j) + analytics (SQLite), cached with Redis",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/recommendations/{user_id}")
def recommendations(user_id: str, top: int = 5):
    """
    Return top recommended campaigns for user_id.

    Flow: (1) Retrieve top 5 most similar users via Milvus vector search.
    (2) Fetch campaigns connected to those users via Neo4j.
    (3) Rank and return results by engagement frequency from the analytics DB.
    """
    if not user_id.strip():
        raise HTTPException(status_code=400, detail="user_id required")
    try:
        results = get_recommendations_for_user(user_id, top_campaigns=min(top, 20))
        return {"user_id": user_id, "recommendations": results}
    except Exception as e:
        logger.exception("recommendations_error", user_id=user_id)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok"}
