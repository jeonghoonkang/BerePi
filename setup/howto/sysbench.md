
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





