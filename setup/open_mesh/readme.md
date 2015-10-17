##### Hint for setup
  - $(cat ~/.ssh/id_rsa.pub) >>/etc/dropbear/authorized_keys;chmod 0600 /etc/dropbear/authorized_keys

````sh
tinyos:NUC:~$ssh-keygen
Generating public/private rsa key pair.
Enter file in which to save the key (/home/tinyos/.ssh/id_rsa):
Enter passphrase (empty for no passphrase):
Enter same passphrase again:
Your identification has been saved in /home/tinyos/.ssh/id_rsa.
Your public key has been saved in /home/tinyos/.ssh/id_rsa.pub.
The key fingerprint is:
SHA256:~~H2h/~~~~~~~~~~~~ tinyos@NUC
The key's randomart image is:
+---[RSA 2048]----+
|     o+.oo oo..  |
|     o .E..+oo . |
|    o + . o.o o  |
|     * . = . +   |
|      ~~~~~~~~.  |
|     . * O + o . |
|      . o = . o .|
|           ... = |
|            o*B..|
+----[SHA256]-----+
````

