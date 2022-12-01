## Install
- brew install barrier


## Issue

<pre>
I had the exact same issue on macOS Monterey (12.0.1) today.

Solved it by running the openssl command described in @4F2E4A2E post.

cd into /Users/<user>/Library/Application Support/barrier/SSL
run in the cmd openssl req -x509 -nodes -days 365 -subj /CN=Barrier -newkey rsa:4096 -keyout Barrier.pem -out Barrier.pem
restart barrier

</pre>
