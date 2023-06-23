import os, sys, time

startTime = time.time()

if len(sys.argv) == 2:
    os.system("whisper %s --language=Korean" % sys.argv[1] )
    endTime = time.time()
    print("file : %s" % sys.argv[1])
    print("processing time : %s" % (endTime - startTime))
elif len(sys.argv) > 1:
    os.system("whisper %s --model=%s --language=Korean --output_dir=%s" % (sys.argv[1], sys.argv[2], sys.argv[2]) )
    endTime = time.time()
    print("file : %s" % sys.argv[1])
    print("processing time : %s" % (endTime - startTime))
else:
    print("require a mp3 file")
    print("python3 run.py <file.mp3>")
    print("python3 run.py <file.mp3> <small,medium,large-v1,large-v2,large>")
