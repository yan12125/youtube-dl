#!/bin/bash

# Run a Python script with multiple versions
# $ ./pythons.sh test/test_download.py TestDownload.test_Generic_62

for i in {python{2.6,2.7,3.2,3.3,3.4,3.5,3.6,3.7},pypy{,3},jython} ; do
    which $i >& /dev/null
    if [ $? != 0 ] ; then
        echo $i not found, skipping...
        continue
    fi
    echo $i -W error $*
    $i -W error $*
done
