How to install Unison on Mac OS El Sierra & Vagrant - for Docker Sync
from https://gist.github.com/parisholley/510f42b9eb64ac9d8d29f0e2a6c8a1a0
----------------------------------------------------------------------
아래 내용중 추가 작업한 내용은,
컴파일이 되지 않아서 Xcode 를 설치해서 컴파일 함
그러나, 다른 MAC OSX 에서  Xcode 를 설치한 후에, 아래 절차를 실행했으나 컴파일 되지 않음
현재는 한번 컴파일된 코드를 복사해서 사용하고 있음
----------------------------------------------------------------------

You can install Unison on the Mac via homebrew (`brew install unison`),
but it's very likely that it won't work properly, resulting in errors like:

```
Unison failed: Uncaught exception Failure("input_value: bad bigarray kind")
Fatal error: Lost connection with the server
```

To solve this problem, you have to make sure that Unison is compiled with
the same version of `ocaml` on both Mac & Vagrant. And this requires some
manual work.

Here are the steps involved:

## Install Unison on Mac OS

```shell
# See: https://github.com/Homebrew/homebrew/issues/37378
brew tap Caskroom/cask
brew install Caskroom/cask/xquartz
cd `brew --prefix`/Homebrew/Library/Taps/homebrew/homebrew-core
git fetch --unshallow # by default, only has latest revision
git checkout b15592e087b968ccd7aee2a7ae1b6998116c2180 Formula/ocaml.rb # check out ocaml-4.05
brew install ocaml # this will take awhile
brew pin ocaml # prevent update/upgrade from blowing this away when repository is upgraded
git reset . && git checkout . # clean up

cd /tmp
wget http://www.seas.upenn.edu/~bcpierce/unison//download/releases/stable/unison-2.48.4.tar.gz
tar -xvzf unison-2.48.4.tar.gz
cd src
make UISTYLE=text
sudo cp unison /usr/local/bin
```

## Install Unison on Vagrant (Ubuntu 14.04)

```bash
cd /tmp
mkdir unison
cd unison
wget http://caml.inria.fr/pub/distrib/ocaml-4.05/ocaml-4.05.0.tar.gz
tar -zxvf ocaml-4.05.0.tar.gz
cd ocaml-4.05.0
./configure
make world.opt
sudo make install

cd ..
wget http://www.seas.upenn.edu/~bcpierce/unison//download/releases/stable/unison-2.48.4.tar.gz
tar -zxvf unison-2.48.4.tar.gz
cd src
make UISTYLE=text NATIVE=false
sudo cp unison /usr/local/bin/
```

That's it. Unison sync should now work properly between Mac OS & Ubuntu
on Vagrant.
