import ollama

# The model name must match the one you downloaded with 'ollama pull'
MODEL = 'llama3:8b'

def get_improvement_tips(tone):
    """Helper function to get context-specific improvement tips."""
    if "Professional" in tone or "Formal" in tone or "Informative" in tone:
        tips = ["- Use clear formatting (like bullet points or numbered lists if appropriate).", "- Add supporting data or statistics if applicable.", "- Ensure the tone is objective and authoritative."]
    elif "Motivational" in tone or "Inspirational" in tone:
        tips = ["- Use more uplifting and powerful words.", "- End with a strong, memorable call-to-action or a thought-provoking question.", "- Add 1-2 relevant, positive emojis to increase warmth."]
    elif "Witty" in tone or "Humorous" in tone or "Sarcastic" in tone:
        tips = ["- Use clever wordplay or a surprising twist in the hook.", "- Keep sentences shorter and punchier for maximum impact.", "- Add 2-3 relevant, funny emojis."]
    else:
        tips = ["- Make the language more conversational, as if talking to a friend.", "- Add 2-3 relevant emojis to show personality.", "- Include 2–3 relevant hashtags to increase reach."]
    return tips

def summarize_text(text_to_summarize):
    """Generates a summary using the local Ollama model."""
    try:
        prompt = f"Summarize the following text in a concise paragraph, focusing on the key points. Do not add any preamble or introductory phrases like 'Here is a summary'. Just provide the summary directly:\n\n{text_to_summarize}"
        response = ollama.generate(model=MODEL, prompt=prompt)
        return response['response'].strip()
    except Exception as e:
        if "connection refused" in str(e).lower(): return "Error: Could not connect to the local Ollama server. Please ensure the Ollama application is running."
        return f"Error during summarization: {e}"

def generate_platform_post(summary, platform, tone):
    """Generates a social media post using the local Ollama model."""
    try:
        prompt = f"""
        You are an expert social media manager creating a post for {platform}. Your tone must be strictly '{tone}'.
        Generate a ready-to-paste post based on this summary: "{summary}".
        IMPORTANT RULES:
        1. Generate plain text only. Do not use markdown formatting like '**' for bolding.
        2. Do not include any introductory phrases like "Here's the post for you:".
        3. Do not include any concluding remarks or explanations about what you have done.
        4. Start the response directly with the title or the first line of the post content.
        5. At the very end of the post, include a line with 3 to 5 relevant hashtags (e.g., #studytips #careerchange #tech).
        """
        response = ollama.generate(model=MODEL, prompt=prompt)
        clean_response = response['response'].strip().replace("**", "")
        return clean_response
    except Exception as e:
        if "connection refused" in str(e).lower(): return "Error: Could not connect to the local Ollama server."
        return f"An error occurred while generating the post: {e}"

def translate_text(text, target_language):
    """Translates text to the target language using the local Ollama model."""
    try:
        prompt = f"Translate the following text into {target_language}. Provide only the translated text, with no extra commentary or labels:\n\n{text}"
        response = ollama.generate(model=MODEL, prompt=prompt)
        return response['response'].strip()
    except Exception as e:
        if "connection refused" in str(e).lower(): return "Error: Could not connect to the local Ollama server."
        return f"Error: Could not translate text: {e}"

def auto_upgrade_post(post_text, platform, tone):
    """Improves a social media post using the local Ollama model based on specific scoring rules."""
    try:
        # --- UPDATED: New, rule-based prompt for the auto-upgrader ---
        prompt = f"""
        You are an expert social media manager. Rewrite and improve the following post for {platform} to **maximize its engagement score**, while keeping the original core message.

        Original Post:
        "{post_text}"

        To maximize the score, you MUST follow these specific rules:
        - **Optimal Length:** The ideal post length is between 40 and 200 characters.
        - **Use Emojis:** Include 2-3 relevant emojis from this list: 😀😁😂🤣😍🔥✨💡🎯👍🙌.
        - **Add Hashtags:** Ensure the post includes 2-3 relevant hashtags at the end.
        - **Include a Call to Action:** If it doesn't have one, add a clear call to action, such as asking a question or using phrases like "follow for more," "share your thoughts," or "link in bio."
        - **Tone:** The tone must be '{tone}'.

        Improved Post (plain text only, no commentary, ready to be copy-pasted):
        """
        
        response = ollama.generate(model=MODEL, prompt=prompt)
        improved_text = response['response'].strip().replace("**", "")
        return improved_text
    except Exception as e:
        if "connection refused" in str(e).lower(): return "Error: Could not connect to the local Ollama server."
        return f"Error during auto-upgrade: {e}"