#! /bin/bash
#ssh-keygen -t rsa -b 4096
#ssh-copy-id -i /home/tinyos/.ssh/id_rsa.pub tinyos@10.0.0.56
watch -n 1 echo '=== LOCAL GPU ==='; nvidia-smi --query-gpu=index,name,memory.used,memory.total --format=csv,noheader; echo ''; echo '=== REMOTE GPU ==='; ssh 10.0.0.56 nvidia-smi --query-gpu=index,name,memory.used,memory.total --format=csv,noheader
