Can't Use apt i.e. /boot is 100% full <br>
NOTE: this is only if you can't use apt to clean up due to a 100% full /boot

0. check current booting image name ``` uname -r ```

1. Get the list of kernel images
* Get the list of kernel images and determine what you can do without. This command will show installed kernels except the currently running one

```
$ sudo dpkg --list 'linux-image*'|awk '{ if ($1=="ii") print $2}'|grep -v `uname -r`

You will get the list of images somethign like below:
linux-image-3.19.0-25-generic
linux-image-3.19.0-56-generic
linux-image-3.19.0-58-generic
linux-image-3.19.0-59-generic
linux-image-3.19.0-61-generic
linux-image-3.19.0-65-generic
linux-image-extra-3.19.0-25-generic
linux-image-extra-3.19.0-56-generic
linux-image-extra-3.19.0-58-generic
linux-image-extra-3.19.0-59-generic
linux-image-extra-3.19.0-61-generic
```
2. Prepare Delete
* Craft a command to delete all files in /boot for kernels that don't matter to you using brace expansion to keep you sane. Remember to exclude the current and two newest kernel images. From above Example, it's

* ``` sudo rm -rf /boot/*-3.19.0-{25,56,58,59,61,65}-* ```
3. Clean up what's making apt grumpy about a partial install.

* ``` sudo apt-get -f install ```
4. Autoremove
* Finally, autoremove to clear out the old kernel image packages that have been orphaned by the manual boot clean.

* ```sudo apt-get autoremove```

5. Update Grub
* ``` sudo update-grub ```

6. Now you can update, install packages
* ``` sudo apt-get update```
