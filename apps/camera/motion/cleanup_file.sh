#!/bin/bash
#Author: github.com/jeonghoonkang

sudo find ./ -maxdepth 1 -name '*.jpg' -print | xargs mv --target-directory=old
