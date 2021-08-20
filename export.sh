#!/usr/bin/env bash

./build.sh

docker save midog2021 | gzip -c > midog2021.tar.gz
