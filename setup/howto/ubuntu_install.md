### Install Ubuntu
- download ubuntu image, iso
  - https://www.ubuntu.com/download/desktop/thank-you?country=KR&version=16.04.3&architecture=amd64
- make bootable usb drive
  - https://rufus.akeo.ie/downloads/rufus-2.11.exe
- Please use mini.iso file to install, other images have some problems for the grub bootload initialization

### grub work
- ls, cat
- prefix = ()/boot/grub

### make usb image from UBUNTU
- sudo apt install usb-creator-gtk 
- ssh -Yf tinyos@192.168.0.24 usb-creator-gtk
   - Before download : https://ubuntu.com/download/desktop/thank-you?version=22.04&architecture=amd64
