#!/bin/bash
sudo find ./ -maxdepth 1 -name '*.jpg' -print | xargs rm
