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
        
        # Set Pinecone API key as environment variable for langchain-pinecone
        os.environ["PINECONE_API_KEY"] = config.PINECONE_API_KEY
        
        # Initialize Google embeddings with 768 dimension (default)
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="models/text-embedding-004",
            google_api_key=config.GEMINI_API_KEY
        )
        
        # Initialize Pinecone vector store
        self.vector_store = PineconeVectorStore(
            index_name=config.PINECONE_INDEX_NAME,
            embedding=self.embeddings
        )
    
    def query_combination_rules(
        self,
        meal_type: str,
        ingredients: List[str],
        top_k: int = 5
    ) -> List[str]:
        """
        Query Pinecone to retrieve ingredient combination rules.
        
        Args:
            meal_type: Type of meal (e.g., "sáng", "trưa", "tối")
            ingredients: List of available ingredients
            top_k: Number of rule documents to retrieve
            
        Returns:
            List of combination rule documents as strings
        """
        # Build query text focusing on ingredient combination rules for meal type
        query_text = f"Quy tắc kết hợp nguyên liệu món ăn Việt Nam bữa {meal_type}"
        if ingredients:
            ingredients_text = ", ".join(ingredients[:5])  # Limit to first 5 ingredients
            query_text += f" với nguyên liệu: {ingredients_text}"
        
        try:
            # Query the vector store for combination rules
            results = self.vector_store.similarity_search(
                query_text,
                k=top_k
            )
            
            # Extract text content from rule documents
            rule_docs = [doc.page_content for doc in results]
            return rule_docs
        
        except Exception as e:
            error_msg = f"Error querying Pinecone for combination rules: {str(e)}"
            print(error_msg)
            raise ValueError(error_msg)
    
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


# Singleton instance
_vector_store_service: VectorStoreService = None


def get_vector_store_service() -> VectorStoreService:
    """Get or create vector store service instance."""
    global _vector_store_service
    if _vector_store_service is None:
        _vector_store_service = VectorStoreService()
    return _vector_store_service

