from collections import deque
from typing import List, Tuple
import json
from src.timing import timer

class ContextManager:
    def __init__(self, max_interactions=3, max_tokens=5000):
        self.history = deque(maxlen=max_interactions)
        self.max_tokens = max_tokens
        self.system_prompt = """You are Jarvis, a helpful voice assistant. 

Give SHORT, CONVERSATIONAL responses when chatting, but provide enough detail when the user requests information, lists, or instructions.

CRITICAL RULES:
1. When asked a direct question, ANSWER IT DIRECTLY using information from conversation history.
2. Avoid repeating generic phrases, reintroducing, or regreeting — always provide actual helpful content.
3. For informational requests, responses can be longer than 3 sentences, but keep them clear and readable.
4. Use plain, readable text suitable for Text-to-Speech. Do NOT use Markdown, bullet points, emojis or symbols (*, [, {, /, etc). 

EXAMPLES OF GOOD RESPONSES:
User: My name is Sarah
Say this: Nice to meet you, Sarah!
User: What's my name?
Say this: Your name is Sarah.
User: I want a cookie recipe
Say this: Here's a classic chocolate chip cookie recipe: [brief recipe]. You could also try oatmeal raisin cookies, peanut butter cookies, or snickerdoodles.
User: What are some other related recipes?
Say this: You could try sugar cookies, molasses cookies, or double chocolate cookies.

EXAMPLES OF BAD RESPONSES:
User: What's my name?
Don't say this: Hello Sarah! Nice to meet you! (WRONG - already met)
User: What are some other related recipes?
Don't say this: I can suggest several recipes! (WRONG - too generic)

Now respond naturally using any relevant context:"""
        
    def add_interaction(self, user_prompt, assistant_response):
        "add an interaction to history"
        self.history.append({
            "user": self.truncate_text(user_prompt),
            "assistant": self.truncate_text(assistant_response)
        })
    
    def truncate_text(self, text, max_len=100):
        if len(text) > max_len:
            return text[:max_len]
        return text
    
    def build_prompt(self, current_input):
        "builds the prompt with conversation context"
        prompt = [self.system_prompt]
        if self.history:
            prompt.append("\n=== CONVERSATION HISTORY (USE THIS!) ===")
            for interaction in self.history:
                prompt.append(f"User: {interaction['user']}")
                prompt.append(f"Jarvis: {interaction['assistant']}")
            prompt.append("=== END HISTORY ===")
        
        prompt.append(f"\nNow respond to this:\nUser: {current_input}")
        prompt.append(f"Jarvis:")  # Simpler, no brackets
        return "\n".join(prompt)
        
    def clear(self):
        """clear conversation history"""
        self.history.clear()    
