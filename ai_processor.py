# ai_processor.py

import streamlit as st 
import google.generativeai as genai

# --- New Summarizer Function (Uses Google Gemini) ---
def summarize_text(text_to_summarize):
    """
    Generates a summary using the Google Gemini API for higher quality.
    """
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"Summarize the following text in one or two concise, engaging sentences: \n\n{text_to_summarize}"
        response = model.generate_content(prompt)
        print("AI Processor: Gemini summarization complete.")
        return response.text
    except Exception as e:
        print(f"Error during summarization: {e}")
        return f"Error during summarization: {e}"

# --- Post Generator Function (Uses Google Gemini) ---
def generate_platform_post_google(summary, platform, brand_voice):
    """
    Generates a social media post using the Google Gemini API, adhering to a specific brand voice.
    """
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

        prompt = f"""
        Act as an expert social media manager.
        Based on the following summary, create a compelling and engaging social media post for the platform: {platform}.

        **Brand Voice Instructions:** You must strictly adhere to the following brand voice: "{brand_voice}".

        **Summary:** "{summary}"

        The post should be ready to copy and paste.
        """
        
        print(f"AI Processor: Generating post for {platform} with brand voice: {brand_voice}...")
        
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        
        post = response.text
        print("AI Processor: Post generation complete.")
        return post

    except Exception as e:
        print(f"An error occurred: {e}")
        return f"An error occurred while generating the post: {e}"