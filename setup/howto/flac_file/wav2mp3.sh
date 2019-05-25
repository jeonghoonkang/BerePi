#!/bin/bash
for i in *.wav; do ffmpeg -i "$i" -ab 320k "${i%.*}.mp3"; done
