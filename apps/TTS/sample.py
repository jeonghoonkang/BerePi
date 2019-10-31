#!/usr/bin/python3

def speak(text):
    from gtts import gTTS
    import os
    tts = gTTS(text=text, lang='ko')
    tts.save("tmp_talk.mp3")
    os.system("omxplayer tmp_talk.mp3")
    os.system("rm -f tmp_talk.mp3")

text = "안녕하세요, 좋은 아침입니다"
speak(text)
