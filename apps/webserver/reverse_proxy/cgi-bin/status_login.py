#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Simple CGI login script to show status.txt on success."""
import cgi
import html
import os

USER = os.environ.get("STATUS_USER", "admin")
PASS = os.environ.get("STATUS_PASS", "secret")
STATUS_FILE = os.environ.get("STATUS_FILE", "status.txt")

form = cgi.FieldStorage()
username = form.getfirst("username")
password = form.getfirst("password")

print("Content-Type: text/html\n")

if username is None or password is None:
    print("<html><body>")
    print("<h1>Login</h1>")
    print("<form method='post'>")
    print("Username: <input type='text' name='username'><br>")
    print("Password: <input type='password' name='password'><br>")
    print("<input type='submit' value='Login'>")
    print("</form>")
    print("</body></html>")
else:
    if username == USER and password == PASS:

        print("<html><body><pre>")
        try:
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    print(html.escape(line), end='')
        except Exception as e:
            print(f"Error reading {html.escape(STATUS_FILE)}: {html.escape(str(e))}")
            print("</pre></body></html>")
    else:
        print("<html><body>")
        print("<p style='color:red'>Invalid credentials</p>")
        print("<a href=''>Try again</a>")
        print("</body></html>")
