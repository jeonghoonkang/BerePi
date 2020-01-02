# TTS (Text-to-Speech)

## TTS systems

1) fetival (open-source) : need a korean language pack
2) espeak (open-source) : need a korean language pack
3) Google TTS API : 
4) Clova Speech Synthesis API
5) gTTS : python Google Translate’s text-to-speech API

## gTTS

1) install

  - install omxplayer, gTTS
  
  ```sudo apt install omxplayer```

  ```sudo pip install gTTS```
  
2) example

```
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
```

## Etc

- [example link](https://github.com/OKCOMTECH/project/tree/master/industry4.0s_TESTBED_DEMO)
