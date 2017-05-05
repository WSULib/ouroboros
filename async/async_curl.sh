#!/bin/bash

for number in {1..1000}
do
curl "http://digidev.library.wayne.edu:9876/" &
done
exit 0