import os
import tempfile
import subprocess
import zipfile
import re
from pathlib import Path

import streamlit as st
from st_copy_to_clipboard import st_copy_to_clipboard

# --- AI imports ---
try:
    from ai_processor import summarize_text, generate_platform_post, translate_text, auto_upgrade_post, get_improvement_tips
except Exception as e:
    st.error(f"Error importing from ai_processor.py: {e}. Make sure the file exists and has no errors.")
    def summarize_text(text): return "Error: Could not summarize."
    def generate_platform_post(s, p, t): return "Error: Could not generate post."
    def translate_text(t, l): return "Error: Could not translate."
    def auto_upgrade_post(p, pl, t): return "Error: Could not auto-upgrade post."
    def get_improvement_tips(t): return ["- Tip 1", "- Tip 2"]

# Whisper import
try:
    import whisper
except Exception:
    whisper = None

# ---------- Utility functions ----------
def transcribe_with_whisper(video_path, model_name="base"):
    if whisper is None: raise RuntimeError("Whisper not available. Install openai-whisper.")
    model = whisper.load_model(model_name)
    result = model.transcribe(video_path, fp16=False)
    return result.get("segments", []), result.get("text", "")

def ffmpeg_cut(input_path, start_s, duration_s, out_path):
    cmd = ["ffmpeg", "-y", "-ss", str(start_s), "-i", str(input_path), "-t", str(duration_s), "-c", "copy", str(out_path)]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError:
        cmd2 = ["ffmpeg", "-y", "-ss", str(start_s), "-i", str(input_path), "-t", str(duration_s), "-c:v", "libx264", "-c:a", "aac", "-preset", "veryfast", str(out_path)]
        subprocess.run(cmd2, check=True)
        return True

def ffmpeg_burn_subtitles(input_clip_path, ass_path, output_clip_path):
    """Burns subtitles from a styled .ass file onto a video clip."""
    safe_ass_path = str(ass_path).replace('\\', '/').replace(':', '\\:')
    vf_string = f"subtitles=filename='{safe_ass_path}'"
    cmd = ["ffmpeg", "-y", "-i", str(input_clip_path), "-vf", vf_string, "-c:a", "copy", str(output_clip_path)]
    print("Running FFmpeg Command:", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Audio copy failed, trying re-encode. Error: {e.stderr.decode()}")
        cmd2 = ["ffmpeg", "-y", "-i", str(input_clip_path), "-vf", vf_string, "-c:a", "aac", str(output_clip_path)]
        print("Running FFmpeg Command (fallback):", " ".join(cmd2))
        try:
            subprocess.run(cmd2, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return True
        except subprocess.CalledProcessError as e2:
            print(f"Error burning subtitles (fallback attempt): {e2.stderr.decode()}")
            return False

def generate_single_clip(clip_index, start_time, duration, target_language, clip_segments, custom_text):
    try:
        temp_dir = Path(tempfile.gettempdir())
        raw_clip_path = temp_dir / f"raw_clip_{clip_index+1}.mp4"
        ass_path = temp_dir / f"subs_{clip_index+1}.ass"
        final_clip_path = temp_dir / f"final_clip_{clip_index+1}.mp4"
        clip_key = f"clip_path_{clip_index}"
        video_file_path = st.session_state.uploaded_file_path
        ffmpeg_cut(video_file_path, start_time, duration, raw_clip_path)
        adjusted_segments = []
        for seg in clip_segments:
            new_start = max(0, seg['start'] - start_time)
            new_end = min(duration, seg['end'] - start_time)
            if new_start < new_end:
                adjusted_segments.append({'start': new_start, 'end': new_end, 'text': seg['text']})
        ass_content, final_translated_text = generate_ass_from_segments(adjusted_segments, target_language)
        with open(ass_path, "w", encoding="utf-8") as ass_file:
            ass_file.write(ass_content)
        ffmpeg_burn_subtitles(raw_clip_path, ass_path, final_clip_path)
        st.session_state[clip_key] = str(final_clip_path)
        return str(final_clip_path), final_translated_text
    except Exception as e:
        st.error(f"Failed to generate Clip {clip_index + 1}: {e}")
        return None, None

def handle_generate_clip_click(clip_index, start_time, duration, target_language, clip_segments):
    text_key = f"custom_text_{clip_index}"
    custom_text = st.session_state[text_key]
    with st.spinner(f"Generating Clip {clip_index+1}..."):
        clip_path, translated_text = generate_single_clip(clip_index, start_time, duration, target_language, clip_segments, custom_text)
        if clip_path and translated_text:
            st.session_state[text_key] = translated_text
            st.toast(f"✅ Clip {clip_index+1} generated successfully!")

def heuristics_engagement_score(post_text):
    score = 50; l = len(post_text)
    if l < 40: score += 5
    elif l < 200: score += 10
    else: score -= 5
    emojis = sum(1 for ch in post_text if ch in "😀😁😂🤣😍🔥✨💡🎯👍🙌"); score += min(10, emojis * 4)
    tags = post_text.count("#"); score += min(10, tags * 3)
    for w in ["subscribe","follow","comment","share","link in bio","join"]:
        if w in post_text.lower(): score += 4
    return max(0, min(100, score))

def score_label(score: int) -> str:
    if score >= 80: return f"🔥 Viral-ready ({score}/100)"
    elif score >= 60: return f"👍 Solid ({score}/100)"
    else: return f"⚠️ Needs improvement ({score}/100)"

def render_tips_box(tone):
    tips = get_improvement_tips(tone)
    tips_html = "<div style='border-left: 3px solid #00FFAA; padding: 0.8rem; border-radius: 8px; background-color: #2D2D35; color: #FAFAFA; margin-bottom: 10px;'>"
    tips_html += "⚠️ This post may need improvements.<br>💡 <b>Try:</b><br>"
    for t in tips: tips_html += f"{t}<br>"
    tips_html += "</div>"
    st.markdown(tips_html, unsafe_allow_html=True)

def generate_ass_from_segments(segments, target_language="English"):
    """Generates a styled .ass subtitle file string from timed segments."""
    font_file_path = os.path.join(os.getcwd(), 'fonts', 'Roboto-Regular.ttf').replace('\\', '/')
    Path(os.path.dirname(font_file_path)).mkdir(parents=True, exist_ok=True)
    if not Path(font_file_path).exists():
        print(f"WARNING: Font file not found at {font_file_path}. Subtitles might not render correctly.")
    ass_header = f"""[Script Info]
Title: Generated Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: None
PlayResX: 1280
PlayResY: 720
Font: {font_file_path}
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Roboto Regular,22,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1.5,1,2,10,10,25,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ass_dialogue = ""
    full_translated_text = []
    for seg in segments:
        start_time = seg.get("start", 0)
        end_time = seg.get("end", 0)
        text = seg.get("text", "").strip()
        start_ass = f"{int(start_time//3600)}:{int((start_time%3600)//60):02}:{int(start_time%60):02}.{int((start_time*100)%100):02}"
        end_ass = f"{int(end_time//3600)}:{int((end_time%3600)//60):02}:{int(end_time%60):02}.{int((end_time*100)%100):02}"
        translated_text = translate_text(text, target_language) if target_language != "Original" else text
        full_translated_text.append(translated_text)
        cleaned_text = translated_text.replace('\n', '\\N').replace('{', '\\{').replace('}', '\\}')
        ass_dialogue += f"Dialogue: 0,{start_ass},{end_ass},Default,,0,0,0,,{cleaned_text}\n"
    return ass_header + ass_dialogue, " ".join(full_translated_text)

# ---------- Streamlit UI ----------
st.set_page_config(page_title="ViralSpark Studio", layout="wide")

st.markdown(
    """<style>
    .clip-title { cursor: pointer; color: white; font-weight: bold; transition: color 0.2s ease-in-out; }
    .clip-title:hover { color: #22c55e; }
    [data-testid="stButton"] > button[type="primary"] { background: linear-gradient(90deg, #00FFAA, #00AAFF); color: #111111; border: none; padding: 0.7rem 1.5rem; border-radius: 10px; font-weight: bold; transition: transform 0.2s ease-in-out; }
    [data-testid="stButton"] > button[type="primary"]:hover { transform: scale(1.03); background: linear-gradient(90deg, #00FFC7, #00B9FF); }
    [data-testid="stButton"] > button:not([type="primary"]) { background-color: #44444A; color: #FFFFFF; border: 1px solid #44444A; padding: 0.7rem 1.5rem; border-radius: 10px; transition: transform 0.2s ease-in-out; }
    [data-testid="stButton"] > button:not([type="primary"]):hover { background-color: #55555E; border-color: #00FFAA; transform: scale(1.03); }
    .st-copy-to-clipboard-container { border: none !important; background: transparent !important; padding: 0 !important; margin-top: 10px; }
    .st-copy-to-clipboard-container input { display: none !important; }
    .st-copy-to-clipboard-container button { background-color: #44444A !important; color: #FFFFFF !important; border: 1px solid #44444A !important; border-radius: 10px !important; width: 100% !important; display: inline-flex !important; justify-content: center; align-items: center; font-size: 1.2em !important; }
    .st-copy-to-clipboard-container button:hover { border-color: #00FFAA !important; color: #00FFAA !important; transform: scale(1.03); }
    .custom-info { background-color: #1F2026; border: 1px solid #00FFAA; border-left-width: 5px; padding: 0.8rem; border-radius: 8px; margin-bottom: 10px; color: #DDDDDD; }
    [data-baseweb="tab-list"] button[aria-selected="true"] { border-bottom-color: #00FFAA !important; color: #00FFAA !important; }
    </style>""",
    unsafe_allow_html=True
)

# THIS IS THE ONLY SECTION THAT HAS BEEN CHANGED
# It correctly renders the header without showing raw HTML code.
st.markdown("""
<div style="display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; padding: 1rem; 
            background: #262730; border-radius: 10px; margin-bottom: 1rem;">
    <h1 style="background: -webkit-linear-gradient(45deg, #00FFAA, #FF00AA); 
                -webkit-background-clip: text; 
                -webkit-text-fill-color: transparent;
                font-size: 2.8em; margin-bottom: 0.5rem;">
        🚀 ViralSpark Studio
    </h1>
    <h3 style="font-weight: 600; color: #DDDDDD; margin: 0;">
        Create once → Publish everywhere 🎯
    </h3>
    <p style="font-size: 1.05rem; color: #AAAAAA; margin-top: 0.5rem;">
        Instantly generate clips, posts, and translated subtitles from any video
    </p>
</div>
""", unsafe_allow_html=True)

default_state = {"stage": "input", "segments": [], "transcript": "", "summary": "", "generated": {}, "clips": [], "uploaded_file": None, "article_text": "", "translated_text": "", "srt_captions": "", "analyze_clicked": False}
for key, val in default_state.items():
    if key not in st.session_state: st.session_state[key] = val

progress_placeholder = st.empty()
def update_progress(step: int):
    steps = ["Step 1️⃣ Transcribing", "Step 2️⃣ Summarizing", "Step 3️⃣ Generating Clips"]
    status_html = "<div style='text-align:center; margin:1rem;'>"
    for i, s in enumerate(steps, 1):
        if i < step: status_html += f"<span style='color:#00FFAA;'>✅ {s}</span> &nbsp; ➡️ &nbsp;"
        elif i == step: status_html += f"<span style='color:#FFD700; font-weight:bold;'>⏳ {s}</span> &nbsp; ➡️ &nbsp;"
        else: status_html += f"<span style='color:#888888;'>{s}</span> &nbsp; ➡️ &nbsp;"
    status_html = status_html.rstrip(" ➡️ &nbsp;") + "</div>"
    progress_placeholder.markdown(status_html, unsafe_allow_html=True)

if st.session_state.stage == "input":
    with st.container(border=True):
        tab1, tab2 = st.tabs(["📂 Upload Media", "📝 Paste Text"])
        with tab1:
            st.markdown('<div class="custom-info">Upload a Video (mp4/mov) or Audio (wav/mp3)</div>', unsafe_allow_html=True)
            uploaded = st.file_uploader("Upload Media File", type=["mp4","mov","wav","mp3"], label_visibility="collapsed")
        with tab2:
            st.markdown('<div class="custom-info">Paste an article, script, or any block of text</div>', unsafe_allow_html=True)
            article_text = st.text_area("Paste Text", height=160, label_visibility="collapsed", placeholder="Paste your content here...")

    _, center_col, _ = st.columns([1, 2, 1])
    with center_col:
        if st.button("🚀 Analyze Content", type="primary", use_container_width=True):
            st.session_state.analyze_clicked = True

    if st.session_state.get('analyze_clicked'):
        if not uploaded and not article_text:
            st.warning("Please upload a file or paste some text first."); st.session_state.analyze_clicked = False
        else:
            try:
                full_text = ""
                if uploaded:
                    update_progress(1)
                    with st.spinner("Transcribing... ⏳"):
                        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded.name).suffix) as tmp:
                            tmp.write(uploaded.getvalue())
                            st.session_state.uploaded_file_path = tmp.name
                        segments, full_text = transcribe_with_whisper(st.session_state.uploaded_file_path, "base")
                        st.session_state.segments = segments
                        st.session_state.transcript = full_text
                        st.session_state.uploaded_file = uploaded
                elif article_text:
                    full_text = article_text; st.session_state.transcript = article_text; st.session_state.article_text = article_text
                
                update_progress(2)
                with st.spinner("Summarizing... 📝"):
                    st.session_state.summary = summarize_text(full_text)

                st.session_state.stage = "create"; st.session_state.analyze_clicked = False; st.rerun()
            except Exception as err:
                st.error(f"Error analyzing content: {err}"); st.session_state.stage = "input"; st.session_state.analyze_clicked = False

if st.session_state.stage == "create":
    update_progress(3)
    source_tab, create_tab = st.tabs(["📝 Source & Clips", "🎨 Creation Studio"])

    with source_tab:
        st.header("📖 Source Content"); st.text_area("Transcript/Article", value=st.session_state.transcript, height=200)
        st.divider()
        with st.expander("✨ Key Summary"): st.write(st.session_state.summary)
        st.divider()
        target_language = st.selectbox("Translate to Language", options=["Original", "English", "Spanish", "French", "German", "Hindi", "Chinese", "Japanese", "Arabic"], key="source_lang_select")
        if target_language != "Original":
            if st.session_state.get("article_text"):
                st.subheader("🌍 Article/Text Translation")
                if st.button("Translate Full Article"):
                    with st.spinner(f"Translating to {target_language}..."):
                        st.session_state.translated_text = translate_text(st.session_state.transcript, target_language)
                if st.session_state.get("translated_text"):
                    st.text_area("Translated Article", value=st.session_state.translated_text, height=150)
                    st.download_button("⬇️ Download Translated Article", data=st.session_state.translated_text, file_name=f"translated_{target_language}.txt")
            elif st.session_state.get("segments"):
                st.subheader("🎬 Full Video Captions (.srt)")
                if st.button("Generate Full Captions"):
                    with st.spinner(f"Generating captions in {target_language}..."):
                        srt_content, _ = generate_ass_from_segments (st.session_state.segments, target_language)
                        st.session_state.srt_captions = srt_content
                if st.session_state.get("srt_captions"):
                    st.text_area("SRT Captions Preview", value=st.session_state.srt_captions, height=150)
                    st.download_button("⬇️ Download Captions (.srt)", data=st.session_state.srt_captions, file_name=f"captions_{target_language}.srt")

        st.divider()
        if st.session_state.get("segments"):
            st.subheader("🎬 Highlights (Auto-labeled Clips)")
            
            clip_settings_cols = st.columns(2)
            with clip_settings_cols[0]:
                clip_len = st.number_input("Clip length (sec)", min_value=0, max_value=60, value=0)
            with clip_settings_cols[1]:
                num_clips = st.number_input("Max auto clips", min_value=0, max_value=10, value=0)

            if clip_len > 0 and num_clips > 0:
                segments_to_display = st.session_state.segments[:num_clips]
                
                for i, seg in enumerate(segments_to_display):
                    with st.container(border=True):
                        text_key = f"custom_text_{i}"
                        clip_key = f"clip_path_{i}"
                        start_time = seg.get("start", 0)
                        end_time = start_time + clip_len
                        
                        current_clip_segments = [s for s in st.session_state.segments if s['start'] < end_time and s['end'] > start_time]
                        
                        if text_key not in st.session_state:
                            st.session_state[text_key] = " ".join([s.get("text", "").strip() for s in current_clip_segments])

                        if st.session_state.get(clip_key):
                            info_col, player_col = st.columns([2, 1])
                            with info_col:
                                st.markdown(f"**Clip {i+1}**")
                                st.caption(f"Time: {start_time:.1f}s to {end_time:.1f}s")
                                st.text_area("Subtitle Text", key=text_key, height=100)
                                st_copy_to_clipboard(st.session_state[text_key], "📋", key=f"copy_subtitle_{i}")
                            
                            with player_col:
                                clip_path = st.session_state[clip_key]
                                if Path(clip_path).exists():
                                    with open(clip_path, "rb") as f:
                                        video_bytes = f.read()
                                    
                                    st.video(video_bytes)
                                    st.download_button(
                                        label="⬇️ Download Clip",
                                        data=video_bytes,
                                        file_name=Path(clip_path).name,
                                        mime="video/mp4",
                                        use_container_width=True
                                    )
                        else:
                            st.markdown(f"**Clip {i+1}**")
                            st.caption(f"Time: {start_time:.1f}s to {end_time:.1f}s")
                            st.text_area("Subtitle Text", key=text_key, height=100)
                            st_copy_to_clipboard(st.session_state[text_key], "📋", key=f"copy_subtitle_{i}")
                            st.button(
                                f"Generate Clip {i+1}",
                                key=f"clip_{i}",
                                use_container_width=True,
                                on_click=handle_generate_clip_click,
                                args=(i, start_time, clip_len, target_language, current_clip_segments)
                            )
                st.divider()
                
                if num_clips > 1:
                    if st.button("⬇️ Generate & Download All as ZIP", use_container_width=True, type="primary"):
                        st.warning("The 'Download All' feature is being updated. Please generate clips individually for now.")

    with create_tab:
        st.header("🎨 Creation Studio")
        with st.expander("✨ Key Summary"):
            st.container(border=True).write(st.session_state.summary)
        st.divider()
        post_target_language = st.selectbox(
            "Translate Post to Language", 
            options=["Original (English)", "Spanish", "French", "German", "Hindi", "Chinese", "Japanese", "Arabic"], 
            key="create_lang_select"
        )
        st.divider()
        tone_preset = st.selectbox("Tone preset", options=["Witty, concise, emojis", "Professional & formal", "Motivational & upbeat", "Casual conversational", "Emotional & heartfelt", "Informative & educational", "Persuasive & promotional", "Humorous & sarcastic", "Inspirational thought-leader", "Storytelling / narrative"])
        st.divider()
        platform_choice = st.selectbox("📌 Select a platform:",["▶️ YouTube", "🎵 TikTok", "🐦 Twitter", "👨‍💼 LinkedIn", "🌍 All Platforms"])
        
        if st.button("✨ Generate Post", use_container_width=True, type="primary"):
            platforms = ["YouTube", "TikTok", "Twitter", "LinkedIn"] if platform_choice=="🌍 All Platforms" else [platform_choice.split(" ",1)[1]]
            with st.spinner("Generating posts..."):
                for p in platforms:
                    base_post = generate_platform_post(st.session_state.summary, p, tone_preset)
                    
                    if post_target_language != "Original (English)":
                        final_post = translate_text(base_post, post_target_language)
                    else:
                        final_post = base_post
                    
                    st.session_state.generated[p] = final_post
        
        if st.session_state.get("generated"):
            for platform, post in st.session_state.generated.items():
                st.subheader(f"{platform} Post"); st.text_area(f"{platform} Post Content", value=post, height=140, key=f"post_text_{platform}")
                st_copy_to_clipboard(post, "📋", key=f"copy_{platform}_post")
                score = heuristics_engagement_score(post); st.markdown(f"**Engagement Score:** {score_label(score)}")
                
                # The two 'if' blocks are now combined into one single block
                if score < 80:
                    # The tips box is now called only once
                    render_tips_box(tone_preset)
                    
                    # The button logic follows inside the same 'if' block
                    if st.button(f"🔧 Auto-Upgrade {platform} Post", key=f"upgrade_{platform}"):
                        with st.spinner("✨ Enhancing post..."):
                            lang = st.session_state.create_lang_select
                            improved_post = auto_upgrade_post(post, platform, tone_preset, lang)
                        st.session_state.generated[platform] = improved_post
                        st.rerun()
    st.divider()
    _, center_col, _ = st.columns([2, 1, 2])
    with center_col:
        if st.button("✨ Analyze New Content", use_container_width=True, type="primary"):
            for key in list(st.session_state.keys()):
                if key != 'stage': del st.session_state[key]
            st.session_state.stage = "input"; st.rerun()