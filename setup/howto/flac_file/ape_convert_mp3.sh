#source from, https://gist.github.com/a-r-d/f4b3304cfba87dcadf01

#first install all the things:
# sudo apt-get install flac ffmpeg mp3splt libav-tools shntool

# Okay first lets do an MP3:
# input files:
#   --> cd.ape
#   --> cp.cue
# (there are other options, like bitrate, but this is just the bare bones)
#avconv -i cd.ape cd.mp3

# Now, split the MP3 file using the CUE file
# this will produce an mp3 file for each track in the same directory
#mp3 split -a -c cd.cue cd.mp3

# Next example: FLAC!
# convert APE to FLAC:
#ffmpeg -i cd.ape cd.flac

# Now, split your FLAC file. Credits for method go to the arch linux wiki:
# https://wiki.archlinux.org/index.php/CUE_Splitting
#shnsplit -f cd.cue -t "%n %t" -o flac cd.flac 

# one more note, you can go directly from APE -> FLAC with shnsplit because that
# tool is fucking awesome, but you need the "mac" encoder. This is a pain in the ass to get
# on ubuntu and ffmeg has the ability to convert APE, so I just show that way here. 
