import streamlit as st
import os
import whisper
import tempfile

from st_copy_to_clipboard import st_copy_to_clipboard
from ai_processor import summarize_text, generate_platform_post_google

st.title("🤖 AI Content Repurposing Tool")
st.info("Upload your content, and let AI create platform-optimized posts for you!")

# --- Session State Initialization ---
if 'summary' not in st.session_state:
    st.session_state.summary = ""
if 'transcript' not in st.session_state:
    st.session_state.transcript = ""

# --- 1. Content Upload Section ---
st.header("Step 1: Upload Your Content")
col1, col2 = st.columns(2)
with col1:
    video_file = st.file_uploader("Upload a Video File", type=["mp4", "mov", "avi", "mpeg"])
with col2:
    article_text = st.text_area("Or Paste an Article/Text Here")

# --- 2. Processing Trigger ---
if st.button("Repurpose Content"):
    if video_file is not None:
        with st.spinner("Transcribing video... This might take a moment."):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file:
                tmp_file.write(video_file.getvalue())
                video_path = tmp_file.name
            
            model = whisper.load_model("base") 
            result = model.transcribe(video_path, fp16=False)
            transcript = result["text"]
            os.remove(video_path)
            st.session_state.transcript = transcript

            with st.spinner("Summarizing transcript..."):
                summary = summarize_text(transcript)
                st.session_state.summary = summary

    elif article_text:
        st.session_state.transcript = ""
        with st.spinner("AI is summarizing your article..."):
            summary = summarize_text(article_text)
            st.session_state.summary = summary
    else:
        st.warning("Please upload a video or paste an article first.")

# --- 3. Display Transcript (if applicable) ---
if st.session_state.transcript:
    # This is the corrected line
    with st.expander("Show Full Video Transcript"):
        st.text_area("Full Transcript:", st.session_state.transcript, height=200)

# --- 4. Display Summary and Generate Posts ---
if st.session_state.summary:
    st.success("Analysis complete!")
    st.subheader("Generated Summary")
    st.write(st.session_state.summary)

    st.subheader("Step 2: Define Your Brand Voice")
    brand_voice_input = st.text_input("e.g., Witty and use emojis, or Professional and formal", value="Witty, concise, and use 2-3 relevant emojis.")

    st.subheader("Step 3: Generate Platform-Specific Posts")
    post_col1, post_col2 = st.columns(2)
    with post_col1:
        if st.button("Generate for Twitter 🐦"):
            with st.spinner("Generating Twitter thread..."):
                twitter_post = generate_platform_post_google(st.session_state.summary, "Twitter", brand_voice_input)
                st.text_area("Twitter Thread:", twitter_post, height=200, key="twitter_text")
                st_copy_to_clipboard(st.session_state.twitter_text)

    with post_col2:
        if st.button("Generate for LinkedIn 👨‍💼"):
            with st.spinner("Generating LinkedIn post..."):
                linkedin_post = generate_platform_post_google(st.session_state.summary, "LinkedIn", brand_voice_input)
                st.text_area("LinkedIn Post:", linkedin_post, height=200, key="linkedin_text")
                st_copy_to_clipboard(st.session_state.linkedin_text)
                
                

