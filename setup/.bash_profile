# .bash_profile
# https://github.com/jeonghoonkang
# bash configuration for MAC OSX

# User specific aliases and functions
C_DEFAULT="\[\033[m\]"
C_CYAN="\[\033[36m\]"
C_GREEN="\[\033[32m\]"
C_YELLOW="\[\033[33m\]"
C_BLUE="\[\033[34m\]"
C_BG_YELLOW="\[\033[43m\]"

alias mvim='/Applications/mvim'
alias rm='rm -i'
alias cp='cp -i'
alias mv='mv -i'
alias ll='ls -FGlh'
alias ls='ls -FG'
alias la='ls -Galh'
alias envtos='env | grep TOS; env | grep MAKERULES;'
alias envtosclass='env | grep CLASSPATH;'
alias envtosmakelocal1='cat /opt/tinyos-1.x/tools/make/Makelocal;'
alias envtosmakelocal2='cat /opt/tinyos-2.x/support/make/Makelocal;'

# Source global definitions
if [ -f /etc/bashrc ]; then
	. /etc/bashrc
fi
alias cdjava='cd /opt/tinyos-1.x/tools/java'
alias cdapps='cd /opt/tinyos-1.x/apps'
alias cdapps2='cd /opt/tinyos-2.x/apps'
alias cdjava2='cd /opt/tinyos-2.x/support/sdk/java'

export MACHNAME=MacProRetina
export TOSROOT=/opt/tinyos-2.x
export TOSDIR=$TOSROOT/tos
export MAKERULES=$TOSROOT/support/make/Makerules

export PS1="$C_CYAN\h:$C_GREEN\W\$$C_DEFAULT"
