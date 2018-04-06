
cat ~/.ssh/id_rsa.pub | ssh -p 9999 tinyos@99.99.com 'cat>>/home/tinyos/.ssh/authorized_keys'
