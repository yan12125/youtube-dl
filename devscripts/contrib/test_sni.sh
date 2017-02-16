#!/bin/bash

# Check whether a given host name requires SNI (Server Name Indication) or not
# Usage: ./test_sni.sh foobar.com

host=$1

echo | openssl s_client -connect ${host}:443 >& /dev/null
without_sni=$?

echo | openssl s_client -connect ${host}:443 -servername $host >& /dev/null
with_sni=$?

[[ $without_sni = 0 ]] && echo Can work without SNI && exit 0
[[ $without_sni = 1 && $with_sni = 0 ]] && echo Need SNI! && exit 0
