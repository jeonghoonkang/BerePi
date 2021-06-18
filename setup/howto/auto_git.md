# try to do
# Automatically push an updated file whenever it is changed

### Linux
1. Make sure `inotify-tools` is installed ([https://github.com/rvoicilas/inotify-tools](https://github.com/rvoicilas/inotify-tools))
2. Configure git as usual
3. Clone the git repository of interest from github and, if necessary, add file you want to monitor
4. Allow username/password to be cached so you aren't asked everytime
```bash
git config credential.helper store
```
5. Open a terminal and navigate, as necessary; issue the following command
```bash
# <<branch>> = branch you are pushing to
# <<file>> = file you want to monitor
inotifywait -q -m -e CLOSE_WRITE --format="git commit -m 'auto commit' %w && git push origin <<branch>>" <<file>> | bash
```
6. In a separate shell, do whatever you want and when monitored file is updated, it will automatically get committed and pushed (as long as the shell with the `inotifywait` command is still active)

### Mac
1. Make sure `fswatch` is installed ([https://github.com/emcrisostomo/fswatch](https://github.com/emcrisostomo/fswatch))
2. Configure git as usual
3. Clone the git repository of interest from github and, if necessary, add file you want to monitor
4. Allow username/password to be cached so you aren't asked everytime
```bash
git config credential.helper store
```
5. Create a script that performs the commit and push (auto_commit_push.sh)
```bash
#!/bin/bash
# <<branch>> = branch you are pushing to
git commit -m "auto commit" $1
git push origin <<branch>>
```
6. Open a terminal and navigate, as necessary; issue the following command
```bash
# <<file>> = file you want to monitor
# <<path/to/auto_commit_push.sh>> = path to the script created above
fswatch -0 <<file>> | xargs -0 -n 1 bash <<path/to/auto_commit_push.sh>>
```
7. In a separate shell, do whatever you want and when monitored file is updated, it will automatically get committed and pushed (as long as the shell with the `fswatch` command is still active)
