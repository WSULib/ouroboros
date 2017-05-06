#!/bin/bash

for number in {1..100}
do
curl "http://digidev.library.wayne.edu:9876/" &
done
exit 0