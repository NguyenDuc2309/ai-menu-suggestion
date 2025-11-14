"""LLM service with multi-provider support (Gemini/OpenAI)."""
from typing import List, Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage, SystemMessage
from google.api_core import exceptions as google_exceptions
from app.config import config
from app.prompts import PARSE_INTENT_PROMPT, GENERATE_MENU_PROMPT, ADJUST_MENU_PROMPT


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
                model="gpt-4.1",  
                temperature=0.8,  
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
            
            import json
            import re
            
            content = response.content.strip()
            print(f"[LLM] parse_intent response (first 500 chars): {content[:500]}")
            
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1).strip()
                print(f"[LLM] Extracted JSON from markdown: {content[:200]}...")
            else:
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
            
            if not content or not content.strip().startswith('{'):
                raise ValueError(f"Response does not contain valid JSON. Content: {content[:200]}")
            
            intent = json.loads(content)
            
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
    
    def generate_menu(
        self,
        ingredients: List[Dict[str, Any]],
        context: List[str],
        meal_type: str,
        num_people: int,
        budget: float,
        previous_dishes: List[str] = None,
        budget_specified: bool = True
    ) -> Dict[str, Any]:
        ingredients_list = []
        for ing in ingredients:
            quantity = ing['quantity']
            base_price = ing['base_price']
            unit = ing.get('unit', 'g')
            ingredients_list.append(
                f"- {ing['name']}: {quantity} {unit} tồn kho (Giá mỗi {unit}: {base_price} VND)"
            )
        ingredients_text = "\n".join(ingredients_list)
        
        context_text = "\n\n".join(context) if context else "Không có quy tắc kết hợp. Hãy tạo menu hợp lý dựa trên nguyên liệu có sẵn."
        
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
                ingredients_text=ingredients_text,
                context_text=context_text,
                previous_dishes_text=previous_dishes_text,
                budget_context=budget_context
            ))
        ])
        
        try:
            print("[LLM] generate_menu: Invoking LLM...")
            response = self.llm.invoke(prompt.format_messages())
            
            import json
            import re
            
            # Get response content
            if not hasattr(response, 'content') or response.content is None:
                raise ValueError("LLM response has no content attribute or content is None")
            
            content = response.content.strip()
            print(f"[LLM] generate_menu response (first 500 chars): {content[:500]}")
            print(f"[LLM] generate_menu response length: {len(content)}")
            
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1).strip()
                print(f"[LLM] Extracted JSON from markdown: {content[:200]}...")
            else:
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
            
            if not content or not content.strip().startswith('{'):
                raise ValueError(f"Response does not contain valid JSON. Content: {content[:200]}")
            
            menu = json.loads(content)
            
            if not isinstance(menu, dict):
                raise ValueError(f"Parsed JSON is not a dictionary: {type(menu)}")
            if "items" not in menu:
                raise ValueError(f"Menu JSON missing 'items' key. Keys: {list(menu.keys())}")
            
            return menu
        except json.JSONDecodeError as e:
            print(f"[LLM] JSONDecodeError: {e}")
            print(f"[LLM] Error at position: {e.pos if hasattr(e, 'pos') else 'N/A'}")
            print(f"[LLM] Full response content: {response.content if 'response' in locals() else 'N/A'}")
            print(f"[LLM] Extracted content that failed: {content if 'content' in locals() else 'N/A'}")
            raise ValueError(f"Failed to generate menu: Invalid JSON response from LLM. Error: {str(e)}")
        except KeyError as e:
            print(f"[LLM] KeyError: Missing key {e}")
            print(f"[LLM] Full response content: {response.content if 'response' in locals() else 'N/A'}")
            print(f"[LLM] Parsed menu keys: {list(menu.keys()) if 'menu' in locals() else 'N/A'}")
            raise ValueError(f"Failed to generate menu: Missing required key in response. {str(e)}")
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
            raise ValueError(f"Failed to generate menu: {str(e)}")
    
    def adjust_menu(
        self,
        menu: Dict[str, Any],
        validation_errors: List[str],
        available_ingredients: List[Dict[str, Any]],
        budget: float,
        needs_enhancement: bool = False
    ) -> Dict[str, Any]:
        errors_text = "\n".join([f"- {err}" for err in validation_errors])
        
        ingredients_list = []
        for ing in available_ingredients:
            quantity = ing['quantity']
            base_price = ing['base_price']
            unit = ing.get('unit', 'g')
            ingredients_list.append(
                f"- {ing['name']}: {quantity} {unit} tồn kho (Giá mỗi {unit}: {base_price} VND)"
            )
        ingredients_text = "\n".join(ingredients_list)
        
        if needs_enhancement:
            min_target = budget * 0.80
            max_target = budget * 0.95
            enhancement_note = f"""⚠️  QUAN TRỌNG: MENU HIỆN TẠI DÙNG QUÁ ÍT NGÂN SÁCH
→ Menu hiện tại chỉ dùng dưới 80% ngân sách ({budget:,.0f} VND)
→ CẦN TĂNG menu lên để đạt TỐI THIỂU {min_target:,.0f} VND (80% budget)
→ Target: {min_target:,.0f} - {max_target:,.0f} VND (80-95% budget)
→ KHÔNG được vượt quá {budget:,.0f} VND

CHIẾN LƯỢC TĂNG MENU (theo thứ tự ưu tiên):
1. Tăng khẩu phần protein/rau trong các món hiện có
2. Thêm món phụ/canh nếu chưa có đủ
3. Thêm tráng miệng/đồ uống (sản phẩm đóng gói sẵn 10-25k) nếu còn dư ngân sách
4. Nâng cấp nguyên liệu (ví dụ: thịt gà → thịt bò nếu budget cho phép)
5. Thêm món mới đa dạng hơn

LƯU Ý: Tăng chất lượng và số lượng món, KHÔNG chỉ tăng giá đơn thuần."""
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
            
            import json
            import re
            
            content = response.content.strip()
            print(f"[LLM] adjust_menu response (first 500 chars): {content[:500]}")
            
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1).strip()
                print(f"[LLM] Extracted JSON from markdown: {content[:200]}...")
            else:
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
            
            if not content or not content.strip().startswith('{'):
                raise ValueError(f"Response does not contain valid JSON. Content: {content[:200]}")
            
            adjusted_menu = json.loads(content)
            
            if not isinstance(adjusted_menu, dict):
                raise ValueError(f"Parsed JSON is not a dictionary: {type(adjusted_menu)}")
            if "items" not in adjusted_menu:
                raise ValueError(f"Menu JSON missing 'items' key. Keys: {list(adjusted_menu.keys())}")
            
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

