"""Pinecone vector store service for knowledge retrieval."""
import os
from typing import List
from langchain_pinecone import Pinecone as PineconeVectorStore
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.config import config


class VectorStoreService:
    """Service for querying Pinecone vector store."""
    
    def __init__(self):
        """Initialize Pinecone vector store."""
        if not config.PINECONE_API_KEY or not config.PINECONE_INDEX_NAME:
            raise ValueError("Pinecone configuration is missing")
        
        if not config.GEMINI_API_KEY:
            raise ValueError("Missing GEMINI_API_KEY")
        
        os.environ["PINECONE_API_KEY"] = config.PINECONE_API_KEY
        
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="models/text-embedding-004",
            google_api_key=config.GEMINI_API_KEY
        )
        
        self.vector_store = PineconeVectorStore(
            index_name=config.PINECONE_INDEX_NAME,
            embedding=self.embeddings
        )
    
    def query_recipes(
        self,
        meal_type: str,
        preferences: List[str],
        budget: int,
        num_people: int,
        top_k: int = 10
    ) -> List[str]:
        """
        Query Pinecone to retrieve recipes/món ăn with ingredients from RAG.
        
        RAG v2: Vector DB chứa recipes hoàn chỉnh với:
        - Tên món ăn
        - Nguyên liệu chi tiết (name, quantity, unit)
        - Combination rules
        - Domain knowledge
        
        Args:
            meal_type: Type of meal (e.g., "sáng", "trưa", "tối")
            preferences: User preferences (e.g., ["gà", "trứng"])
            budget: Budget in VND
            num_people: Number of people
            top_k: Number of recipes to retrieve
            
        Returns:
            List of recipe documents as strings
        """
        # Build query for RAG
        query_text = f"Món ăn Việt Nam cho bữa {meal_type}, {num_people} người, ngân sách {budget} VND"
        
        if preferences:
            preferences_text = ", ".join(preferences)
            query_text += f", sở thích: {preferences_text}"
        
        try:
            print(f"[RAG] Querying recipes: {query_text}")
            results = self.vector_store.similarity_search(
                query_text,
                k=top_k
            )
            
            recipe_docs = [doc.page_content for doc in results]
            print(f"[RAG] Retrieved {len(recipe_docs)} recipes from vector DB")
            return recipe_docs
        
        except Exception as e:
            error_msg = f"Error querying Pinecone for recipes: {str(e)}"
            print(error_msg)
            raise ValueError(error_msg)
    
    def query_combination_rules(
        self,
        meal_type: str,
        ingredients: List[str],
        top_k: int = 5
    ) -> List[str]:
        """
        DEPRECATED: Use query_recipes() instead.
        Kept for backward compatibility only.
        """
        print("[DEPRECATED] query_combination_rules is deprecated, use query_recipes instead")
        return self.query_recipes(meal_type, ingredients, 0, 1, top_k)
    
    def query_knowledge(
        self,
        meal_type: str,
        ingredients: List[str],
        top_k: int = 5
    ) -> List[str]:
        """
        Deprecated: Use query_combination_rules instead.
        Kept for backward compatibility.
        """
        return self.query_combination_rules(meal_type, ingredients, top_k)


_vector_store_service: VectorStoreService = None


def get_vector_store_service() -> VectorStoreService:
    """Get or create vector store service instance."""
    global _vector_store_service
    if _vector_store_service is None:
        _vector_store_service = VectorStoreService()
    return _vector_store_service

