#!/bin/bash
apt -qq update
apt -qq install -y openssh-server
apt -qq -y install tmux mc htop 
pip install -q glances
