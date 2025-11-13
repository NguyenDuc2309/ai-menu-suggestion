"""LLM service with multi-provider support (Gemini/OpenAI)."""
import time
from typing import List, Dict, Any, Tuple, Union
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage, SystemMessage
from google.api_core import exceptions as google_exceptions
from app.config import config
from app.prompts import PARSE_INTENT_PROMPT, GENERATE_MENU_PROMPT, ADJUST_MENU_PROMPT


class LLMService:
    """Service for LLM operations with configurable provider (Gemini/OpenAI)."""
    
    def _extract_token_usage(self, response) -> Dict[str, Any]:
        """Extract token usage from response (works for both Gemini and OpenAI)."""
        token_usage = {}
        
        # Try OpenAI format first (response_metadata.token_usage)
        try:
            if hasattr(response, "response_metadata") and response.response_metadata:
                if isinstance(response.response_metadata, dict):
                    token_usage = response.response_metadata.get("token_usage", {})
                elif hasattr(response.response_metadata, "get"):
                    token_usage = response.response_metadata.get("token_usage", {})
                else:
                    # Try accessing as attribute
                    token_usage = getattr(response.response_metadata, "token_usage", {})
                
                if token_usage:
                    return token_usage if isinstance(token_usage, dict) else {}
        except Exception as e:
            pass
        
        # Try Gemini format (usage_metadata)
        try:
            if hasattr(response, "usage_metadata"):
                usage_metadata = response.usage_metadata
                if usage_metadata:
                    prompt_tokens = getattr(usage_metadata, "prompt_token_count", None)
                    completion_tokens = getattr(usage_metadata, "candidates_token_count", None)
                    total_tokens = getattr(usage_metadata, "total_token_count", None)
                    
                    # Check if any token count exists
                    if prompt_tokens is not None or completion_tokens is not None or total_tokens is not None:
                        return {
                            "prompt_tokens": prompt_tokens or 0,
                            "completion_tokens": completion_tokens or 0,
                            "total_tokens": total_tokens or (prompt_tokens or 0) + (completion_tokens or 0)
                        }
        except Exception as e:
            pass
        
        # Try accessing response_metadata as dict directly
        try:
            if hasattr(response, "response_metadata"):
                metadata = response.response_metadata
                if isinstance(metadata, dict):
                    token_usage = metadata.get("token_usage", {})
                    if token_usage:
                        return token_usage
        except Exception as e:
            pass
        
        # Try to get from additional_kwargs (some LangChain versions store it here)
        try:
            if hasattr(response, "additional_kwargs"):
                kwargs = response.additional_kwargs
                if isinstance(kwargs, dict):
                    if "usage_metadata" in kwargs:
                        usage_meta = kwargs["usage_metadata"]
                        if isinstance(usage_meta, dict):
                            prompt_tokens = usage_meta.get("prompt_token_count", 0)
                            completion_tokens = usage_meta.get("candidates_token_count", 0)
                            total_tokens = usage_meta.get("total_token_count", 0)
                            if total_tokens > 0:
                                return {
                                    "prompt_tokens": prompt_tokens,
                                    "completion_tokens": completion_tokens,
                                    "total_tokens": total_tokens
                                }
        except Exception as e:
            pass
        
        # If token usage not found, return empty dict (don't log to reduce noise)
        return {}
    
    def __init__(self):
        """Initialize LLM based on LLM_PROVIDER config."""
        self.provider = config.LLM_PROVIDER
        
        if self.provider == "gemini":
            if not config.GEMINI_API_KEY:
                raise ValueError("Missing GEMINI_API_KEY (required when LLM_PROVIDER=gemini)")
            
            self.llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-pro",
                temperature=0.7,
                google_api_key=config.GEMINI_API_KEY,
                max_retries=0  # Disable retry to fail fast on quota errors
            )
            self.use_system_message = False  # Gemini doesn't support SystemMessage
            
        elif self.provider == "openai":
            if not config.OPENAI_API_KEY:
                raise ValueError("Missing OPENAI_API_KEY (required when LLM_PROVIDER=openai)")
            
            self.llm = ChatOpenAI(
                model="gpt-4-turbo-preview",  # Using gpt-4-turbo as gpt-4.1 doesn't exist
                temperature=0.7,
                openai_api_key=config.OPENAI_API_KEY,
                max_retries=0  # Disable retry to fail fast on errors
            )
            self.use_system_message = True  # OpenAI supports SystemMessage
            
        else:
            raise ValueError(f"Invalid LLM_PROVIDER: {self.provider}. Must be 'gemini' or 'openai'")
    
    def parse_intent(self, user_input: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        start_time = time.time()
        prompt = ChatPromptTemplate.from_messages([
            HumanMessage(content=PARSE_INTENT_PROMPT.format(user_input=user_input))
        ])
        
        try:
            response = self.llm.invoke(prompt.format_messages())
            elapsed_time = time.time() - start_time
            
            import json
            import re
            
            # Get response content
            content = response.content.strip()
            print(f"[LLM] parse_intent response (first 500 chars): {content[:500]}")
            
            # Try to extract JSON from markdown code blocks
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1).strip()
                print(f"[LLM] Extracted JSON from markdown: {content[:200]}...")
            else:
                # Try to find JSON object by finding balanced braces
                start_idx = content.find('{')
                if start_idx != -1:
                    brace_count = 0
                    end_idx = start_idx
                    for i in range(start_idx, len(content)):
                        if content[i] == '{':
                            brace_count += 1
                        elif content[i] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                end_idx = i
                                break
                    if brace_count == 0:
                        content = content[start_idx:end_idx + 1].strip()
                        print(f"[LLM] Extracted JSON from text (balanced braces): {content[:200]}...")
                    else:
                        print(f"[LLM] Unbalanced braces, trying to parse entire content")
                else:
                    print("[LLM] No '{' found, trying to parse entire content")
            
            # Validate content before parsing
            if not content or not content.strip().startswith('{'):
                raise ValueError(f"Response does not contain valid JSON. Content: {content[:200]}")
            
            intent = json.loads(content)
            
            # Validate intent structure
            if not isinstance(intent, dict):
                raise ValueError(f"Parsed JSON is not a dictionary: {type(intent)}")
            
            # Extract token usage
            token_usage = self._extract_token_usage(response)
            
            usage_info = {
                "time_seconds": round(elapsed_time, 3),
                "tokens": token_usage
            }
            
            return intent, usage_info
        except json.JSONDecodeError as e:
            elapsed_time = time.time() - start_time
            print(f"[LLM] JSONDecodeError: {e}")
            print(f"[LLM] Error at position: {e.pos if hasattr(e, 'pos') else 'N/A'}")
            print(f"[LLM] Full response content: {response.content if 'response' in locals() else 'N/A'}")
            print(f"[LLM] Extracted content that failed: {content if 'content' in locals() else 'N/A'}")
            raise ValueError(f"Failed to parse intent: Invalid JSON response from LLM. Error: {str(e)}")
        except google_exceptions.ResourceExhausted as e:
            elapsed_time = time.time() - start_time
            print(f"[LLM] parse_intent: ResourceExhausted caught immediately - Quota exceeded!")
            print(f"[LLM] parse_intent: Error details: {e}")
            raise ValueError(f"API quota exceeded: {str(e)}")
        except Exception as e:
            elapsed_time = time.time() - start_time
            error_str = str(e).lower()
            error_type = type(e).__name__
            print(f"[LLM] Unexpected error parsing intent ({self.provider}): {error_type}: {e}")
            import traceback
            print(f"[LLM] Traceback: {traceback.format_exc()}")
            if 'response' in locals():
                print(f"[LLM] Full response content: {response.content}")
            if 'content' in locals():
                print(f"[LLM] Extracted content: {content[:500]}")
            # Check if it's a quota/rate limit error (works for both Gemini and OpenAI)
            if ("quota" in error_str or "429" in error_str or "resourceexhausted" in error_str or 
                "ratelimit" in error_str or "rate_limit" in error_str or error_type == "RateLimitError"):
                raise ValueError(f"API quota/rate limit exceeded: {str(e)}")
            # Check if it's an authentication error
            if ("api key" in error_str or "api_key" in error_str or "unauthorized" in error_str or 
                "401" in error_str or "authentication" in error_str or error_type == "AuthenticationError"):
                raise ValueError(f"API authentication error: {str(e)}")
            raise ValueError(f"Failed to parse intent: {str(e)}")
    
    def generate_menu(
        self,
        ingredients: List[Dict[str, Any]],
        context: List[str],
        cuisine: str,
        budget: float
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        start_time = time.time()
        # Format ingredients list
        # base_price is price per unit, quantity is stock
        ingredients_list = []
        for ing in ingredients:
            quantity = ing['quantity']  # stock quantity
            base_price = ing['base_price']  # price per unit
            unit = ing.get('unit', 'g')
            ingredients_list.append(
                f"- {ing['name']}: {quantity} {unit} tồn kho (Giá mỗi {unit}: {base_price} VND)"
            )
        ingredients_text = "\n".join(ingredients_list)
        
        # Format combination rules context
        context_text = "\n\n".join(context) if context else "No combination rules available."
        
        prompt = ChatPromptTemplate.from_messages([
            HumanMessage(content=GENERATE_MENU_PROMPT.format(
                cuisine=cuisine,
                budget=budget,
                ingredients_text=ingredients_text,
                context_text=context_text
            ))
        ])
        
        try:
            print("[LLM] generate_menu: Invoking LLM...")
            response = self.llm.invoke(prompt.format_messages())
            elapsed_time = time.time() - start_time
            
            import json
            import re
            
            # Get response content
            if not hasattr(response, 'content') or response.content is None:
                raise ValueError("LLM response has no content attribute or content is None")
            
            content = response.content.strip()
            print(f"[LLM] generate_menu response (first 500 chars): {content[:500]}")
            print(f"[LLM] generate_menu response length: {len(content)}")
            
            # Try to extract JSON from markdown code blocks
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1).strip()
                print(f"[LLM] Extracted JSON from markdown: {content[:200]}...")
            else:
                # Try to find JSON object by finding balanced braces
                start_idx = content.find('{')
                if start_idx != -1:
                    brace_count = 0
                    end_idx = start_idx
                    for i in range(start_idx, len(content)):
                        if content[i] == '{':
                            brace_count += 1
                        elif content[i] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                end_idx = i
                                break
                    if brace_count == 0:
                        content = content[start_idx:end_idx + 1].strip()
                        print(f"[LLM] Extracted JSON from text (balanced braces): {content[:200]}...")
                    else:
                        print(f"[LLM] Unbalanced braces, trying to parse entire content")
                else:
                    print("[LLM] No '{' found, trying to parse entire content")
            
            # Validate content before parsing
            if not content or not content.strip().startswith('{'):
                raise ValueError(f"Response does not contain valid JSON. Content: {content[:200]}")
            
            menu = json.loads(content)
            
            # Validate menu structure
            if not isinstance(menu, dict):
                raise ValueError(f"Parsed JSON is not a dictionary: {type(menu)}")
            if "items" not in menu:
                raise ValueError(f"Menu JSON missing 'items' key. Keys: {list(menu.keys())}")
            
            # Extract token usage
            token_usage = self._extract_token_usage(response)
            
            usage_info = {
                "time_seconds": round(elapsed_time, 3),
                "tokens": token_usage
            }
            
            return menu, usage_info
        except json.JSONDecodeError as e:
            elapsed_time = time.time() - start_time
            print(f"[LLM] JSONDecodeError: {e}")
            print(f"[LLM] Error at position: {e.pos if hasattr(e, 'pos') else 'N/A'}")
            print(f"[LLM] Full response content: {response.content if 'response' in locals() else 'N/A'}")
            print(f"[LLM] Extracted content that failed: {content if 'content' in locals() else 'N/A'}")
            raise ValueError(f"Failed to generate menu: Invalid JSON response from LLM. Error: {str(e)}")
        except KeyError as e:
            elapsed_time = time.time() - start_time
            print(f"[LLM] KeyError: Missing key {e}")
            print(f"[LLM] Full response content: {response.content if 'response' in locals() else 'N/A'}")
            print(f"[LLM] Parsed menu keys: {list(menu.keys()) if 'menu' in locals() else 'N/A'}")
            raise ValueError(f"Failed to generate menu: Missing required key in response. {str(e)}")
        except google_exceptions.ResourceExhausted as e:
            elapsed_time = time.time() - start_time
            print(f"[LLM] generate_menu: ResourceExhausted caught immediately - Quota exceeded!")
            print(f"[LLM] generate_menu: Error details: {e}")
            raise ValueError(f"API quota exceeded: {str(e)}")
        except Exception as e:
            elapsed_time = time.time() - start_time
            error_str = str(e).lower()
            error_type = type(e).__name__
            print(f"[LLM] Unexpected error generating menu ({self.provider}): {error_type}: {e}")
            import traceback
            print(f"[LLM] Traceback: {traceback.format_exc()}")
            if 'response' in locals():
                print(f"[LLM] Full response content: {response.content}")
            if 'content' in locals():
                print(f"[LLM] Extracted content: {content[:500]}")
            # Check if it's a quota/rate limit error (works for both Gemini and OpenAI)
            if ("quota" in error_str or "429" in error_str or "resourceexhausted" in error_str or 
                "ratelimit" in error_str or "rate_limit" in error_str or error_type == "RateLimitError"):
                raise ValueError(f"API quota/rate limit exceeded: {str(e)}")
            # Check if it's an authentication error
            if ("api key" in error_str or "api_key" in error_str or "unauthorized" in error_str or 
                "401" in error_str or "authentication" in error_str or error_type == "AuthenticationError"):
                raise ValueError(f"API authentication error: {str(e)}")
            raise ValueError(f"Failed to generate menu: {str(e)}")
    
    def adjust_menu(
        self,
        menu: Dict[str, Any],
        validation_errors: List[str],
        available_ingredients: List[Dict[str, Any]],
        budget: float
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        start_time = time.time()
        errors_text = "\n".join([f"- {err}" for err in validation_errors])
        
        # Format available ingredients
        # base_price is price per unit, quantity is stock
        ingredients_list = []
        for ing in available_ingredients:
            quantity = ing['quantity']  # stock quantity
            base_price = ing['base_price']  # price per unit
            unit = ing.get('unit', 'g')
            ingredients_list.append(
                f"- {ing['name']}: {quantity} {unit} tồn kho (Giá mỗi {unit}: {base_price} VND)"
            )
        ingredients_text = "\n".join(ingredients_list)
        
        prompt = ChatPromptTemplate.from_messages([
            HumanMessage(content=ADJUST_MENU_PROMPT.format(
                menu=menu,
                errors_text=errors_text,
                ingredients_text=ingredients_text,
                budget=budget
            ))
        ])
        
        try:
            response = self.llm.invoke(prompt.format_messages())
            elapsed_time = time.time() - start_time
            
            import json
            import re
            
            # Get response content
            content = response.content.strip()
            print(f"[LLM] adjust_menu response (first 500 chars): {content[:500]}")
            
            # Try to extract JSON from markdown code blocks
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1).strip()
                print(f"[LLM] Extracted JSON from markdown: {content[:200]}...")
            else:
                # Try to find JSON object by finding balanced braces
                start_idx = content.find('{')
                if start_idx != -1:
                    brace_count = 0
                    end_idx = start_idx
                    for i in range(start_idx, len(content)):
                        if content[i] == '{':
                            brace_count += 1
                        elif content[i] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                end_idx = i
                                break
                    if brace_count == 0:
                        content = content[start_idx:end_idx + 1].strip()
                        print(f"[LLM] Extracted JSON from text (balanced braces): {content[:200]}...")
                    else:
                        print(f"[LLM] Unbalanced braces, trying to parse entire content")
                else:
                    print("[LLM] No '{' found, trying to parse entire content")
            
            # Validate content before parsing
            if not content or not content.strip().startswith('{'):
                raise ValueError(f"Response does not contain valid JSON. Content: {content[:200]}")
            
            adjusted_menu = json.loads(content)
            
            # Validate menu structure
            if not isinstance(adjusted_menu, dict):
                raise ValueError(f"Parsed JSON is not a dictionary: {type(adjusted_menu)}")
            if "items" not in adjusted_menu:
                raise ValueError(f"Menu JSON missing 'items' key. Keys: {list(adjusted_menu.keys())}")
            
            # Extract token usage
            token_usage = self._extract_token_usage(response)
            
            usage_info = {
                "time_seconds": round(elapsed_time, 3),
                "tokens": token_usage
            }
            
            return adjusted_menu, usage_info
        except json.JSONDecodeError as e:
            elapsed_time = time.time() - start_time
            print(f"[LLM] JSONDecodeError: {e}")
            print(f"[LLM] Error at position: {e.pos if hasattr(e, 'pos') else 'N/A'}")
            print(f"[LLM] Full response content: {response.content if 'response' in locals() else 'N/A'}")
            print(f"[LLM] Extracted content that failed: {content if 'content' in locals() else 'N/A'}")
            raise ValueError(f"Failed to adjust menu: Invalid JSON response from LLM. Error: {str(e)}")
        except KeyError as e:
            elapsed_time = time.time() - start_time
            print(f"[LLM] KeyError: Missing key {e}")
            print(f"[LLM] Full response content: {response.content if 'response' in locals() else 'N/A'}")
            print(f"[LLM] Parsed menu keys: {list(adjusted_menu.keys()) if 'adjusted_menu' in locals() else 'N/A'}")
            raise ValueError(f"Failed to adjust menu: Missing required key in response. {str(e)}")
        except google_exceptions.ResourceExhausted as e:
            elapsed_time = time.time() - start_time
            print(f"[LLM] adjust_menu: ResourceExhausted caught immediately - Quota exceeded!")
            print(f"[LLM] adjust_menu: Error details: {e}")
            raise ValueError(f"API quota exceeded: {str(e)}")
        except Exception as e:
            elapsed_time = time.time() - start_time
            error_str = str(e).lower()
            error_type = type(e).__name__
            print(f"[LLM] Unexpected error adjusting menu ({self.provider}): {error_type}: {e}")
            import traceback
            print(f"[LLM] Traceback: {traceback.format_exc()}")
            if 'response' in locals():
                print(f"[LLM] Full response content: {response.content}")
            if 'content' in locals():
                print(f"[LLM] Extracted content: {content[:500]}")
            # Check if it's a quota/rate limit error (works for both Gemini and OpenAI)
            if ("quota" in error_str or "429" in error_str or "resourceexhausted" in error_str or 
                "ratelimit" in error_str or "rate_limit" in error_str or error_type == "RateLimitError"):
                raise ValueError(f"API quota/rate limit exceeded: {str(e)}")
            # Check if it's an authentication error
            if ("api key" in error_str or "api_key" in error_str or "unauthorized" in error_str or 
                "401" in error_str or "authentication" in error_str or error_type == "AuthenticationError"):
                raise ValueError(f"API authentication error: {str(e)}")
            raise ValueError(f"Failed to adjust menu: {str(e)}")


# Singleton instance
_llm_service: LLMService = None


def get_llm_service() -> LLMService:
    """Get or create LLM service instance."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service

