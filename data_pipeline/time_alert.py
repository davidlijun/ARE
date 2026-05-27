import streamlit as st
import time
from datetime import datetime

def play_alert_sound():
    # A short 'Ding' sound encoded in base64
    audio_html = """
    <audio autoplay>
      <source src="https://www.soundjay.com/buttons/beep-01a.mp3" type="audio/mpeg">
    </audio>
    """
    st.markdown(audio_html, unsafe_allow_html=True)

# UI Logic for your Sidebar
target_time = datetime.strptime("15:32:00", "%H:%M:%S").time()
now = datetime.now().time()

if now < target_time:
    st.sidebar.warning(f"⏳ Gatekeeper Locked. Window opens at {target_time.strftime('%H:%M:%S')}")
    st.sidebar.write(f"Current Time: {now.strftime('%H:%M:%S')}")
    time.sleep(1)
    st.rerun() # Refresh the app every second to check the time again
else:
    play_alert_sound()
    st.sidebar.success("🚀 GATEKEEPER OPEN: Execute Now!")
    st.balloons()  # Visual celebration to grab attention
    st.stop()