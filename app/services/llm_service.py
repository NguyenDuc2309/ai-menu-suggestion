"""LLM service with multi-provider support (Gemini/OpenAI)."""
import json
import re
from typing import List, Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage, SystemMessage
from google.api_core import exceptions as google_exceptions
from app.config import config
from app.prompts import PARSE_INTENT_PROMPT, GENERATE_MENU_PROMPT, ADJUST_MENU_PROMPT, SQL_WHERE_CLAUSE_PROMPT


def clean_json_string(content: str) -> str:
    """Clean and fix common JSON errors from LLM responses."""
    content = content.strip()
    
    # Extract JSON object by finding balanced braces first (handles nested objects)
    start_idx = content.find('{')
    if start_idx != -1:
        brace_count = 0
        end_idx = start_idx
        for i in range(start_idx, len(content)):
            char = content[i]
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i
                    break
        if brace_count == 0:
            content = content[start_idx:end_idx + 1].strip()
    
    # Remove markdown code blocks (if still present after extraction)
    json_match = re.search(r'```(?:json)?\s*(\{.*\})\s*```', content, re.DOTALL)
    if json_match:
        # Re-extract with balanced braces
        extracted = json_match.group(1)
        start_idx = extracted.find('{')
        if start_idx != -1:
            brace_count = 0
            end_idx = start_idx
            for i in range(start_idx, len(extracted)):
                if extracted[i] == '{':
                    brace_count += 1
                elif extracted[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i
                        break
            if brace_count == 0:
                content = extracted[start_idx:end_idx + 1].strip()
    
    # Fix common JSON issues
    # 1. Remove trailing commas before } or ]
    content = re.sub(r',(\s*[}\]])', r'\1', content)
    
    # 2. Remove comments (// or /* */)
    content = re.sub(r'//.*?$', '', content, flags=re.MULTILINE)
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    
    # 3. Fix single quotes to double quotes for simple string values (conservative)
    # Only fix simple cases like 'value' not complex nested strings
    content = re.sub(r":\s*'([^']*)'(\s*[,}\]])", r': "\1"\2', content)
    
    return content


def parse_json_with_fallback(content: str, context: str = "") -> Dict[str, Any]:
    """Parse JSON with multiple fallback strategies."""
    original_content = content
    
    # Strategy 1: Try direct parse
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    
    # Strategy 2: Clean and try again
    try:
        cleaned = clean_json_string(content)
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    
    # Strategy 3: Try to extract JSON object more aggressively
    try:
        # Find the largest JSON object
        start_idx = content.find('{')
        if start_idx != -1:
            # Try to find matching closing brace
            brace_count = 0
            end_idx = start_idx
            for i in range(start_idx, len(content)):
                char = content[i]
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i
                        break
            
            if brace_count == 0:
                extracted = content[start_idx:end_idx + 1]
                cleaned = clean_json_string(extracted)
                return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    
    # Strategy 4: Log detailed error info
    error_msg = f"Failed to parse JSON{': ' + context if context else ''}"
    print(f"[LLM] {error_msg}")
    print(f"[LLM] Original content length: {len(original_content)}")
    
    # Try to find the error position and show context
    try:
        json.loads(original_content)
    except json.JSONDecodeError as e:
        print(f"[LLM] JSON error: {e}")
        if hasattr(e, 'pos') and e.pos is not None:
            error_start = max(0, e.pos - 150)
            error_end = min(len(original_content), e.pos + 150)
            error_context = original_content[error_start:error_end]
            
            # Show line number
            line_num = original_content[:e.pos].count('\n') + 1
            col_num = e.pos - original_content.rfind('\n', 0, e.pos) - 1
            
            print(f"[LLM] Error at line {line_num}, column {col_num} (position {e.pos}):")
            print(f"[LLM] ...{error_context}...")
            print(f"[LLM] {' ' * (len('...') + min(150, e.pos - error_start))}^")
        else:
            print(f"[LLM] Original content (first 1000 chars): {original_content[:1000]}")
    except Exception:
        print(f"[LLM] Original content (first 1000 chars): {original_content[:1000]}")
    
    raise ValueError(f"{error_msg}. Invalid JSON response from LLM.")


def format_ingredients_text(ingredients: List[Dict[str, Any]]) -> str:
    """Format ingredients list into text with header/footer for LLM prompt."""
    ingredients_list = []
    for idx, ing in enumerate(ingredients, 1):
        quantity = ing['quantity']
        base_price = ing['base_price']
        unit = ing.get('unit', 'g')
        ingredients_list.append(
            f"{idx}. {ing['name']}: Giá {base_price} VND/{unit} (Tồn kho: {quantity} {unit})"
        )
    return f"""=== DANH SÁCH NGUYÊN LIỆU CÓ SẴN (CHỈ ĐƯỢC DÙNG CÁC NGUYÊN LIỆU NÀY) ===

{chr(10).join(ingredients_list)}

⚠️ LƯU Ý QUAN TRỌNG: CHỈ ĐƯỢC DÙNG CÁC NGUYÊN LIỆU TRÊN. KHÔNG ĐƯỢC TỰ TẠO THÊM NGUYÊN LIỆU MỚI. === """


def validate_menu_ingredients(menu: Dict[str, Any], available_ingredients: List[Dict[str, Any]], context: str = "menu") -> None:
    """Validate that all ingredients in menu are in available_ingredients list."""
    available_names = {ing['name'].lower() for ing in available_ingredients}
    invalid_ingredients = []
    
    for item in menu.get("items", []):
        for ing in item.get("ingredients", []):
            ing_name = ing.get("name", "").strip()
            if not ing_name:
                continue
            if ing_name.lower() not in available_names:
                invalid_ingredients.append(ing_name)
    
    if invalid_ingredients:
        invalid_list = ", ".join(set(invalid_ingredients))
        error_msg = "AI returned invalid ingredients not in the available list"
        print(f"[LLM] VALIDATION FAILED: Invalid ingredients: {invalid_list}")
        raise ValueError(error_msg)


class LLMService:
    """Service for LLM operations with configurable provider (Gemini/OpenAI)."""
    
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
                max_retries=0  
            )
            self.use_system_message = False 
            
        elif self.provider == "openai":
            if not config.OPENAI_API_KEY:
                raise ValueError("Missing OPENAI_API_KEY (required when LLM_PROVIDER=openai)")
            
            self.llm = ChatOpenAI(
                model="gpt-4o-mini",  
                temperature=0.7,  
                openai_api_key=config.OPENAI_API_KEY,
                max_retries=0 
            )
            self.use_system_message = True  
            
        else:
            raise ValueError(f"Invalid LLM_PROVIDER: {self.provider}. Must be 'gemini' or 'openai'")
    
    def parse_intent(self, user_input: str) -> Dict[str, Any]:
        prompt = ChatPromptTemplate.from_messages([
            HumanMessage(content=PARSE_INTENT_PROMPT.format(user_input=user_input))
        ])
        
        try:
            response = self.llm.invoke(prompt.format_messages())
            
            if not hasattr(response, 'content') or response.content is None:
                raise ValueError("LLM response has no content attribute or content is None")
            
            content = response.content.strip()
            print(f"[LLM] parse_intent response (first 500 chars): {content[:500]}")
            
            intent = parse_json_with_fallback(content, "parse_intent")
            
            if not isinstance(intent, dict):
                raise ValueError(f"Parsed JSON is not a dictionary: {type(intent)}")
            
            if "budget" not in intent:
                intent["budget"] = None
            if "num_people" not in intent:
                intent["num_people"] = 1
            if "preferences" not in intent:
                intent["preferences"] = []
            
            return intent
        except json.JSONDecodeError as e:
            print(f"[LLM] JSONDecodeError: {e}")
            print(f"[LLM] Error at position: {e.pos if hasattr(e, 'pos') else 'N/A'}")
            print(f"[LLM] Full response content: {response.content if 'response' in locals() else 'N/A'}")
            print(f"[LLM] Extracted content that failed: {content if 'content' in locals() else 'N/A'}")
            raise ValueError(f"Failed to parse intent: Invalid JSON response from LLM. Error: {str(e)}")
        except google_exceptions.ResourceExhausted as e:
            print(f"[LLM] parse_intent: ResourceExhausted caught immediately - Quota exceeded!")
            print(f"[LLM] parse_intent: Error details: {e}")
            raise ValueError(f"API quota exceeded: {str(e)}")
        except Exception as e:
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
    
    def generate_sql_where_clause(
        self,
        budget: int,
        meal_type: str,
        num_people: int,
        preferences: List[str]
    ) -> str:
        """Generate SQL WHERE clause from intent to filter ingredients."""
        preferences_str = ", ".join(preferences) if preferences else "none"
        
        prompt = ChatPromptTemplate.from_messages([
            HumanMessage(content=SQL_WHERE_CLAUSE_PROMPT.format(
                budget=budget,
                meal_type=meal_type,
                num_people=num_people,
                preferences=preferences_str
            ))
        ])
        
        try:
            print("[LLM] generate_sql_where_clause: Invoking LLM...")
            response = self.llm.invoke(prompt.format_messages())
            
            if not hasattr(response, 'content') or response.content is None:
                raise ValueError("LLM response has no content")
            
            content = response.content.strip()
            
            # Clean up response
            content = re.sub(r'```(?:sql)?\s*', '', content)
            content = re.sub(r'WHERE\s+', '', content, flags=re.IGNORECASE)
            content = content.strip('`').strip()
            
            print(f"[LLM] generate_sql_where_clause: {content[:150]}")
            return content
            
        except google_exceptions.ResourceExhausted as e:
            print(f"[LLM] generate_sql_where_clause: ResourceExhausted")
            raise ValueError(f"API quota exceeded: {str(e)}")
        except Exception as e:
            error_str = str(e).lower()
            error_type = type(e).__name__
            print(f"[LLM] Error generating SQL ({self.provider}): {error_type}: {e}")
            if ("quota" in error_str or "429" in error_str or "resourceexhausted" in error_str):
                raise ValueError(f"API quota exceeded: {str(e)}")
            if ("api key" in error_str or "unauthorized" in error_str or "401" in error_str):
                raise ValueError(f"API authentication error: {str(e)}")
            raise ValueError(f"Failed to generate SQL: {str(e)}")
    
    def generate_menu(
        self,
        ingredients: List[Dict[str, Any]],
        context: List[str],
        meal_type: str,
        num_people: int,
        budget: float,
        previous_dishes: List[str] = None,
        budget_specified: bool = True,
        preferences: List[str] | None = None,
    ) -> Dict[str, Any]:
        ingredients_text = format_ingredients_text(ingredients)
        
        context_text = "\n\n".join(context) if context else "Không có quy tắc kết hợp. Hãy tạo menu hợp lý dựa trên nguyên liệu có sẵn."

        if preferences:
            preferences_text = ", ".join(preferences)
        else:
            preferences_text = "Không có (user không yêu cầu cụ thể)."
        
        if previous_dishes and len(previous_dishes) > 0:
            dishes_list = ", ".join(previous_dishes)
            previous_dishes_text = f"""🔔 LƯU Ý QUAN TRỌNG: TRÁNH LẶP MÓN ĂN
Người dùng này gần đây đã được gợi ý các món: {dishes_list}
→ Hãy gợi ý các món KHÁC, sáng tạo và đa dạng hơn. Đừng lặp lại các món trên!"""
        else:
            previous_dishes_text = ""
        
        if not budget_specified:
            budget_context = f"""⚠️  LƯU Ý: Người dùng KHÔNG nhập ngân sách.
→ Hệ thống đã tự đặt ngân sách PHÙ HỢP với loại bữa và số người: {budget:,.0f} VND.
→ Hãy tạo menu ngon, hợp lý và KHÔNG ĐƯỢC VƯỢT quá {budget:,.0f} VND."""
        else:
            budget_context = f"""✓ Người dùng YÊU CẦU ngân sách {budget:,.0f} VND.
→ Cố gắng tận dụng 70-85% ngân sách (khoảng {int(budget * 0.7):,}-{int(budget * 0.85):,} VND)."""
        
        prompt = ChatPromptTemplate.from_messages([
            HumanMessage(content=GENERATE_MENU_PROMPT.format(
                meal_type=meal_type,
                num_people=num_people,
                budget=budget,
                preferences_text=preferences_text,
                ingredients_text=ingredients_text,
                context_text=context_text,
                previous_dishes_text=previous_dishes_text,
                budget_context=budget_context
            ))
        ])
        
        try:
            print("[LLM] generate_menu: Invoking LLM...")
            response = self.llm.invoke(prompt.format_messages())
            
            if not hasattr(response, 'content') or response.content is None:
                raise ValueError("LLM response has no content attribute or content is None")
            
            content = response.content.strip()
            print(f"[LLM] generate_menu response (first 500 chars): {content[:500]}")
            print(f"[LLM] generate_menu response length: {len(content)}")
            
            menu = parse_json_with_fallback(content, "generate_menu")
            
            if not isinstance(menu, dict):
                raise ValueError(f"Parsed JSON is not a dictionary: {type(menu)}")
            if "items" not in menu:
                raise ValueError(f"Menu JSON missing 'items' key. Keys: {list(menu.keys())}")
            
            validate_menu_ingredients(menu, ingredients, "menu")
            return menu
        except ValueError as e:
            error_msg = str(e)
            if "Failed to parse JSON" in error_msg or "Invalid JSON" in error_msg:
                print(f"[LLM] JSON parsing failed: {error_msg}")
                print(f"[LLM] Full response content: {response.content if 'response' in locals() else 'N/A'}")
                print(f"[LLM] Extracted content that failed: {content if 'content' in locals() else 'N/A'}")
                raise ValueError(f"Failed to generate menu: {error_msg}")
            raise
        except json.JSONDecodeError as e:
            print(f"[LLM] JSONDecodeError: {e}")
            print(f"[LLM] Error at position: {e.pos if hasattr(e, 'pos') else 'N/A'}")
            print(f"[LLM] Full response content: {response.content if 'response' in locals() else 'N/A'}")
            print(f"[LLM] Extracted content that failed: {content if 'content' in locals() else 'N/A'}")
            raise ValueError(f"Failed to generate: Invalid JSON response from LLM. Error: {str(e)}")
        except KeyError as e:
            print(f"[LLM] KeyError: Missing key {e}")
            print(f"[LLM] Full response content: {response.content if 'response' in locals() else 'N/A'}")
            print(f"[LLM] Parsed menu keys: {list(menu.keys()) if 'menu' in locals() else 'N/A'}")
            raise ValueError(f"Failed to generate: Missing required key in response. {str(e)}")
        except google_exceptions.ResourceExhausted as e:
            print(f"[LLM] generate_menu: ResourceExhausted caught immediately - Quota exceeded!")
            print(f"[LLM] generate_menu: Error details: {e}")
            raise ValueError(f"API quota exceeded: {str(e)}")
        except Exception as e:
            error_str = str(e).lower()
            error_type = type(e).__name__
            print(f"[LLM] Unexpected error generating menu ({self.provider}): {error_type}: {e}")
            import traceback
            print(f"[LLM] Traceback: {traceback.format_exc()}")
            if 'response' in locals():
                print(f"[LLM] Full response content: {response.content}")
            if 'content' in locals():
                print(f"[LLM] Extracted content: {content[:500]}")
            if ("quota" in error_str or "429" in error_str or "resourceexhausted" in error_str or 
                "ratelimit" in error_str or "rate_limit" in error_str or error_type == "RateLimitError"):
                raise ValueError(f"API quota/rate limit exceeded: {str(e)}")
            if ("api key" in error_str or "api_key" in error_str or "unauthorized" in error_str or 
                "401" in error_str or "authentication" in error_str or error_type == "AuthenticationError"):
                raise ValueError(f"API authentication error: {str(e)}")
            raise ValueError(f"Failed to generate: {str(e)}")
    
    def adjust_menu(
        self,
        menu: Dict[str, Any],
        validation_errors: List[str],
        available_ingredients: List[Dict[str, Any]],
        budget: float,
        needs_enhancement: bool = False
    ) -> Dict[str, Any]:
        errors_text = "\n".join([f"- {err}" for err in validation_errors])
        
        ingredients_text = format_ingredients_text(available_ingredients)
        
        if needs_enhancement:
            min_target = budget * 0.75
            max_target = budget * 0.95
            enhancement_note = f"""⚠️  QUAN TRỌNG: MENU HIỆN TẠI DÙNG QUÁ ÍT NGÂN SÁCH
→ Menu hiện tại chỉ dùng dưới 75% ngân sách ({budget:,.0f} VND)
→ CẦN TĂNG menu lên để đạt TỐI THIỂU {min_target:,.0f} VND (75% budget)
→ Target: {min_target:,.0f} - {max_target:,.0f} VND (75-95% budget)
→ KHÔNG được vượt quá {budget:,.0f} VND

CHIẾN LƯỢC TĂNG MENU (theo thứ tự ưu tiên):
1. Tăng khẩu phần protein/rau trong các món hiện có
2. Thêm món phụ/canh nếu chưa có đủ
3. Nâng cấp nguyên liệu (ví dụ: thịt gà → thịt bò nếu budget cho phép)
4. Thêm món mới đa dạng hơn từ nguyên liệu CÓ SẴN
5. Thêm tráng miệng/đồ uống CHỈ KHI có nguyên liệu phù hợp trong danh sách

⚠️ LƯU Ý QUAN TRỌNG: Tăng chất lượng và số lượng món, KHÔNG chỉ tăng giá đơn thuần.
CHỈ DÙNG NGUYÊN LIỆU CÓ TRONG DANH SÁCH. KHÔNG TỰ TẠO THÊM."""
        else:
            enhancement_note = ""
        
        prompt_content = ADJUST_MENU_PROMPT.format(
            menu=menu,
            errors_text=errors_text,
            ingredients_text=ingredients_text,
            budget=budget,
            enhancement_note=enhancement_note
        )
        
        prompt = ChatPromptTemplate.from_messages([
            HumanMessage(content=prompt_content)
        ])
        
        try:
            response = self.llm.invoke(prompt.format_messages())
            
            if not hasattr(response, 'content') or response.content is None:
                raise ValueError("LLM response has no content attribute or content is None")
            
            content = response.content.strip()
            print(f"[LLM] adjust_menu response (first 500 chars): {content[:500]}")
            
            adjusted_menu = parse_json_with_fallback(content, "adjust_menu")
            
            if not isinstance(adjusted_menu, dict):
                raise ValueError(f"Parsed JSON is not a dictionary: {type(adjusted_menu)}")
            if "items" not in adjusted_menu:
                raise ValueError(f"Menu JSON missing 'items' key. Keys: {list(adjusted_menu.keys())}")
            
            validate_menu_ingredients(adjusted_menu, available_ingredients, "adjusted menu")
            return adjusted_menu
        except json.JSONDecodeError as e:
            print(f"[LLM] JSONDecodeError: {e}")
            print(f"[LLM] Error at position: {e.pos if hasattr(e, 'pos') else 'N/A'}")
            print(f"[LLM] Full response content: {response.content if 'response' in locals() else 'N/A'}")
            print(f"[LLM] Extracted content that failed: {content if 'content' in locals() else 'N/A'}")
            raise ValueError(f"Failed to adjust menu: Invalid JSON response from LLM. Error: {str(e)}")
        except KeyError as e:
            print(f"[LLM] KeyError: Missing key {e}")
            print(f"[LLM] Full response content: {response.content if 'response' in locals() else 'N/A'}")
            print(f"[LLM] Parsed menu keys: {list(adjusted_menu.keys()) if 'adjusted_menu' in locals() else 'N/A'}")
            raise ValueError(f"Failed to adjust menu: Missing required key in response. {str(e)}")
        except google_exceptions.ResourceExhausted as e:
            print(f"[LLM] adjust_menu: ResourceExhausted caught immediately - Quota exceeded!")
            print(f"[LLM] adjust_menu: Error details: {e}")
            raise ValueError(f"API quota exceeded: {str(e)}")
        except Exception as e:
            error_str = str(e).lower()
            error_type = type(e).__name__
            print(f"[LLM] Unexpected error adjusting menu ({self.provider}): {error_type}: {e}")
            import traceback
            print(f"[LLM] Traceback: {traceback.format_exc()}")
            if 'response' in locals():
                print(f"[LLM] Full response content: {response.content}")
            if 'content' in locals():
                print(f"[LLM] Extracted content: {content[:500]}")
            if ("quota" in error_str or "429" in error_str or "resourceexhausted" in error_str or 
                "ratelimit" in error_str or "rate_limit" in error_str or error_type == "RateLimitError"):
                raise ValueError(f"API quota/rate limit exceeded: {str(e)}")
            if ("api key" in error_str or "api_key" in error_str or "unauthorized" in error_str or 
                "401" in error_str or "authentication" in error_str or error_type == "AuthenticationError"):
                raise ValueError(f"API authentication error: {str(e)}")
            raise ValueError(f"Failed to adjust menu: {str(e)}")


_llm_service: LLMService = None


def get_llm_service() -> LLMService:
    """Get or create LLM service instance."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service

