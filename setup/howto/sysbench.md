sysbench --test=cpu run

sysbench fileio --file-total-size=15G --file-test-mode=rndrw --time=300 --max-requests=0 prepare
sysbench fileio --file-total-size=15G --file-test-mode=rndrw --time=300 --max-requests=0 run
sysbench fileio --file-total-size=15G --file-test-mode=rndrw --time=300 --max-requests=0 cleanup


<pre>
fit-let / MiniPC MINI2

tinyos@toshome-fit001:~$ sysbench --test=cpu run
WARNING: the --test option is deprecated. You can pass a script name or path on the command line without any options.
sysbench 1.0.18 (using system LuaJIT 2.1.0-beta3)

Running the test with following options:
Number of threads: 1
Initializing random number generator from current time


Prime numbers limit: 10000

Initializing worker threads...

Threads started!

CPU speed:
    events per second:  1178.88

General statistics:
    total time:                          10.0009s
    total number of events:              11792

Latency (ms):
         min:                                    0.84
         avg:                                    0.85
         max:                                    1.40
         95th percentile:                        0.89
         sum:                                 9997.24

Threads fairness:
    events (avg/stddev):           11792.0000/0.00
    execution time (avg/stddev):   9.9972/0.00

</pre>


<pre>

RaspberryPi Zero

pi@mins-gate ~ $ sysbench --test=cpu run
sysbench 0.4.12:  multi-threaded system evaluation benchmark

Running the test with following options:
Number of threads: 1

Doing CPU performance benchmark

Threads started!
Done.

Maximum prime number checked in CPU test: 10000


Test execution summary:
    total time:                          374.2803s
    total number of events:              10000
    total time taken by event execution: 374.2455
    per-request statistics:
         min:                                 34.83ms
         avg:                                 37.42ms
         max:                                665.24ms
         approx.  95 percentile:              39.24ms

Threads fairness:
    events (avg/stddev):           10000.0000/0.00
    execution time (avg/stddev):   374.2455/0.00

</pre>

<pre>
DELL P-Edge R230

tinyos@bigws-PEdge-R230 ~ $ sysbench --test=cpu run
sysbench 0.4.12:  multi-threaded system evaluation benchmark

Running the test with following options:
Number of threads: 1

Doing CPU performance benchmark

Threads started!
Done.

Maximum prime number checked in CPU test: 10000


Test execution summary:
    total time:                          8.7698s
    total number of events:              10000
    total time taken by event execution: 8.7680
    per-request statistics:
         min:                                  0.85ms
         avg:                                  0.88ms
         max:                                  2.09ms
         approx.  95 percentile:               0.91ms

Threads fairness:
    events (avg/stddev):           10000.0000/0.00
    execution time (avg/stddev):   8.7680/0.00
</pre>

<pre>
NUC-i7

tinyos@DESKTOP-C9UTUR7 ~ $ sysbench --test=cpu run
WARNING: the --test option is deprecated. You can pass a script name or path on the command line without any options.
sysbench 1.0.11 (using system LuaJIT 2.1.0-beta3)

Running the test with following options:
Number of threads: 1
Initializing random number generator from current time


Prime numbers limit: 10000

Initializing worker threads...

Threads started!

CPU speed:
    events per second:  1354.22

General statistics:
    total time:                          10.0027s
    total number of events:              13548

Latency (ms):
         min:                                  0.70
         avg:                                  0.74
         max:                                  1.55
         95th percentile:                      0.81
         sum:                               9966.16

Threads fairness:
    events (avg/stddev):           13548.0000/0.00
    execution time (avg/stddev):   9.9662/0.00
</pre>

<pre>
ACERPC MINI

tinyos@DESKTOP-5F3J3LU:/mnt/d/devel/docker_run/vol/nextcloud$ sysbench --test=cpu run                                                     
WARNING: the --test option is deprecated. You can pass a script name or path on the command line without any options.                     
sysbench 1.0.18 (using system LuaJIT 2.1.0-beta3)                                                                                                                   
Running the test with following options:                                                                                                  
Number of threads: 1                                                                                                                      
Initializing random number generator from current time                                                                                            
Prime numbers limit: 10000                                                                                                                                         
Initializing worker threads...                                                                                                                                     
Threads started!       
CPU speed:   
events per second:   698.18     
General statistics:      
total time:                          10.0005s                                                                                             
total number of events:              6984                                                                                                                           
Latency (ms):                                                                                                                                      
    min:                                    1.00
    avg:                                    1.43
    max:                                    4.82
    95th percentile:                        1.82
    sum:                                 9989.01
    Threads fairness:                                                                                                                             
    events (avg/stddev):           6984.0000/0.00                                                                                             
    execution time (avg/stddev):   9.9890/0.00            
</pre>
