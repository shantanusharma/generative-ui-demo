import os
import json
from typing import List, Literal, Union
from pydantic import BaseModel, ValidationError, model_validator
from google import genai
from google.genai import types

# ==========================================
# 1. The Design System (Critic's Knowledge Base)
# ==========================================
from pydantic import BaseModel, ValidationError, model_validator
from typing import List, Literal, Union

BrandColors = Literal["brand-primary", "brand-secondary", "neutral-100", "neutral-900"]
SpacingTokens = Literal["4px", "8px", "16px", "24px", "32px"]

class Button(BaseModel):
    type: Literal["Button"]
    text: str
    color: BrandColors
    padding: SpacingTokens

    @model_validator(mode='after')
    def check_brand_rules(self):
        if self.color == 'brand-primary' and self.padding != '16px':
            raise ValueError(f"Brand Violation: Primary buttons MUST have 16px padding. Got {self.padding}.")
        return self

class Header(BaseModel):
    type: Literal["Header"]
    text: str
    color: BrandColors

class Container(BaseModel):
    type: Literal["Container"]
    padding: SpacingTokens
    # FIX: We remove the recursive 'Container' reference here to prevent the SDK from infinitely looping
    children: List[Union['Button', 'Header']]

class UIResponse(BaseModel):
    root: Container

# ==========================================
# 2. Setup the New SDK (Generator Agent)
# ==========================================
# The client automatically picks up the GEMINI_API_KEY environment variable
client = genai.Client()

# ==========================================
# 3. The Orchestrator Loop
# ==========================================
def generate_ui(user_intent: str, max_retries: int = 3):
    print(f"🎯 User Intent: {user_intent}\n")
    
    prompt = f"""
    You are a UI Generator Agent. Your job is to generate a JSON representation of a UI component tree.
    You MUST adhere strictly to the provided schema. Do not invent colors, padding, or components.
    
    User Intent: {user_intent}
    """

    for attempt in range(1, max_retries + 1):
        print(f"--- Attempt {attempt} ---")
        print("[Generator] Drafting UI...")
        
        # 1. Generate using the new google.genai SDK
        # Passing the Pydantic model directly to `response_schema` creates a server-side guardrail!
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=UIResponse, 
                temperature=0.7
            )
        )
        
        raw_json = response.text
        print(f"[Generator Output]:\n{raw_json}\n")
        
        # 2. Critique (Validation)
        try:
            print("[Critic] Validating against complex Brand Rules...")
            parsed_json = json.loads(raw_json)
            
            # Pydantic evaluates our custom @model_validators here
            valid_ui = UIResponse(**parsed_json) 
            
            print("✅ [Critic] Success! UI matches all structural and complex brand constraints.")
            return valid_ui.model_dump()
            
        except ValidationError as e:
            # 3. Handle Hallucinations & Route Feedback
            error_details = e.errors()
            print(f"❌ [Critic] Validation Failed! Found {len(error_details)} brand violations.")
            
            feedback = "The previous generated JSON was invalid. Please fix the following errors:\n"
            for err in error_details:
                location = " -> ".join([str(loc) for loc in err['loc']])
                feedback += f"- At '{location}': {err['msg']}\n"
                
            print(f"[Feedback Route]:\n{feedback}")
            prompt += f"\n\nPREVIOUS ERROR FEEDBACK:\n{feedback}\nPlease generate a corrected JSON."

    print("🚨 [System] Max retries reached. Could not generate a brand-safe UI.")
    return None

# ==========================================
# Run it
# ==========================================
if __name__ == "__main__":
    # We purposefully ask for an invalid padding on a primary button to trigger the Critic loop
    intent = "Create a layout with a dark neutral header saying 'Welcome' and a primary brand button saying 'Login' with 8px padding."
    final_ui = generate_ui(intent)
    
    if final_ui:
        print("\n🚀 Final Approved UI State ready for Frontend Rendering:")
        print(json.dumps(final_ui, indent=2))
