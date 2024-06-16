# How to check ubuntu sleep status

## After setup disable sleep 
<pre>
$ sudo systemctl status sleep.target
○ sleep.target - Sleep
     Loaded: loaded (/lib/systemd/system/sleep.target; static)
     Active: inactive (dead)
       Docs: man:systemd.special(7)
     
$ sudo systemctl status suspend.target
○ suspend.target
     Loaded: masked (Reason: Unit suspend.target is masked.)
     Active: inactive (dead)
     
$ sudo systemctl status hybrid-sleep.target
○ hybrid-sleep.target - Hybrid Suspend+Hibernate
     Loaded: loaded (/lib/systemd/system/hybrid-sleep.target; static)
     Active: inactive (dead)
       Docs: man:systemd.special(7)
</pre>

## How to disable sleep in ubuntu

<pre>
$ sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target
Created symlink /etc/systemd/system/sleep.target → /dev/null.
Created symlink /etc/systemd/system/suspend.target → /dev/null.
Created symlink /etc/systemd/system/hibernate.target → /dev/null.
Created symlink /etc/systemd/system/hybrid-sleep.target → /dev/null.
</pre>

## Before setup disable sleep
<pre>
$ sudo systemctl status sleep.target
○ sleep.target - Sleep
     Loaded: loaded (/lib/systemd/system/sleep.target; static)
     Active: inactive (dead)
       Docs: man:systemd.special(7)
</pre>
