#!/bin/sh

writeFile='log/test/test_res_write.txt'
readFile='log/test/test_res_read.txt'
randReadFile='log/test/test_res_rand_read.txt'

echo 'We are ready to start testing our program\n\n'
echo 'In the beginning we will run some SCADA scripts, that will write a value into registers'
sleep 3

#redirecting stdout to a file
exec 6>&1
exec > $writeFile

#                czas port wart 
python plc_write.py 20 100 &
sleep .5

python plc_write.py 25 200 2 &
python plc_write.py 30 300 4 &
sleep 1

python plc_write.py 35 400 8 &
python plc_write.py 40 500 16 &
python plc_write.py 45 600 32 &
sleep .5

python plc_write.py 50 700 64 &
python plc_write.py 55 800 128 &
python plc_write.py 60 900 256 &
sleep .5

python plc_write.py 65 1000 512 &
python plc_write.py 70 1100 458 &
python plc_write.py 80 1200 586 &
sleep .5

python plc_write.py 85 1300 23 &
python plc_write.py 95 1400 & 
python plc_write.py 90 1500 10 &
python plc_write.py 100 1600 586 
sleep .5

#reseting stdout, because we will need to make one more redirection to another file
exec 1>&6 6>&-

echo '\n\nNow we will read values from those registers'
sleep 3

#make stdout redirection to another text file
exec 6>&1
exec > $readFile

#                port quantity
python plc_read.py 100 5
python plc_read.py 200 5
python plc_read.py 300 5
python plc_read.py 400 5
python plc_read.py 500 5
python plc_read.py 600 5
python plc_read.py 700 5
python plc_read.py 800 5
python plc_read.py 900 5
python plc_read.py 1000 5
python plc_read.py 1100 5
python plc_read.py 1200 5
python plc_read.py 1300 5
python plc_read.py 1400 5
python plc_read.py 1500 5
python plc_read.py 1600 5

#close this redirection
exec 1>&6 6>&-

echo '\n\nThe last part of our testing'
echo 'We will read some values from random registers'
sleep 3

#make stdout redirection one last time
exec 6>&1
exec > $randReadFile

python plc_random_read.py
python plc_random_read.py 200 601 1201 5623 1602

#close that one
exec 1>&6 6>&-

echo '\n\nThank you. Bye!'

