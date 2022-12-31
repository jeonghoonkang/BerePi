## Install
- brew install barrier


## Issue

<pre>

(error) ssl certificate doesn't exist: /Users/tinyos/Library/Application Support/barrier/SSL/Barrier.pem

I had the exact same issue on macOS Monterey (12.0.1) today.

Solved it by running the openssl command described in @4F2E4A2E post.

cd into /Users/<user>/Library/Application Support/barrier/SSL
run in the cmd 
openssl req -x509 -nodes -days 365 -subj /CN=Barrier -newkey rsa:4096 -keyout Barrier.pem -out Barrier.pem
restart barrier

(other direction)
openssl req -x509 -nodes -days 365 -subj /CN=barrier -newkey rsa:4096 -keyout barrier.pem -out barrier.pem
openssl x509 -fingerprint -sha1 -noout -in barrier.pem > Fingerprints/Local.txt
sed -e "s/.*=//" -i Fingerprints/Local.txt

</pre>
