<pre>
s1="sysbench --test=cpu run" ;
s2="ioping -q -c 10 -s 8k -W ." ;
order='date';
START=`date`; PERIOD=30; 
when=$START
while true; do $order; echo ""; $s1; echo ""; $s2; 
echo "---------- split line ----------  (info)"$PERIOD" secs peroid  "; 
echo " first-shot run time:"; echo $when; echo " ----loop end---- "; 
sleep $PERIOD; 
done; 
</pre>

- sysbench --test=cpu run

- sysbench fileio --file-total-size=15G --file-test-mode=rndrw --time=300 --max-requests=0 prepare
- sysbench fileio --file-total-size=15G --file-test-mode=rndrw --time=300 --max-requests=0 run
- sysbench fileio --file-total-size=15G --file-test-mode=rndrw --time=300 --max-requests=0 cleanup

- hdd 속도 hdd speed
  - ioping -q -c 10 -s 8k -W .

<pre>
sysbench --test=cpu run && ioping -q -c 10 -s 8k -W .
</pre>



|머신|cpu 속도| 추가 정보  |
|------|---|---|
|RaspberryPi5 | 2724.77 ev/sec | Cortex-A76, 4core |
|RaspberryPi4 | 1488.30 ev/sec | aarch64, Cortex-A72, 4core |
|Ryzen 5 | 4841.66 ev/sec | AMD Ryzen 5 5600G with Radeon Graphics, x86_64, 12core |
|MSI ryzen | 5043 ev/sec | * |
|fit-let      | 1178.88 ev/sec | * |
|RaspberryPi Zero   | 26  ev/sec | * |
|DELL P-Edge R230   | 1140 ev/sec | * |
|NUC-i7       | 1354.22   ev/sec | * |
|ACERPC MINI       | 698.18   ev/sec | * |
|Fit pc home  | 13343    ev/sec | * |
|iMAC       | 3810686.73 ev/sec | Intel(R) Core(TM) i5-8500 CPU @ 3.00GHz (by sysctl -a) |



<pre>
RaspberryPi4 4G RAM with SSD
tinyos@rpuntu-001:~$ sysbench --test=cpu run
WARNING: the --test option is deprecated. You can pass a script name or path on the command line without any options.
sysbench 1.0.20 (using system LuaJIT 2.1.0-beta3)

Running the test with following options:
Number of threads: 1
Initializing random number generator from current time


Prime numbers limit: 10000

Initializing worker threads...

Threads started!

CPU speed:
    events per second:  1488.30

General statistics:
    total time:                          10.0005s
    total number of events:              14891

Latency (ms):
         min:                                    0.67
         avg:                                    0.67
         max:                                    1.66
         95th percentile:                        0.69
         sum:                                 9993.73

Threads fairness:
    events (avg/stddev):           14891.0000/0.00
    execution time (avg/stddev):   9.9937/0.00
</pre>


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
tinyos@jh-RPuntu:~$ sysbench --test=cpu run
WARNING: the --test option is deprecated. You can pass a script name or path on the command line without any options.
sysbench 1.0.20 (using system LuaJIT 2.1.0-beta3)

Running the test with following options:
Number of threads: 1
Initializing random number generator from current time


Prime numbers limit: 10000

Initializing worker threads...

Threads started!

CPU speed:
    events per second:  1488.82

General statistics:
    total time:                          10.0005s
    total number of events:              14895

Latency (ms):
         min:                                    0.67
         avg:                                    0.67
         max:                                    1.39
         95th percentile:                        0.68
         sum:                                 9991.60

Threads fairness:
    events (avg/stddev):           14895.0000/0.00
    execution time (avg/stddev):   9.9916/0.00

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


<pre>
tinyos@toshome-fit001:~$ sysbench fileio --file-total-size=15G --file-test-mode=rndrw --time=300 --max-requests=0 run
sysbench 1.0.18 (using system LuaJIT 2.1.0-beta3)

Running the test with following options:
Number of threads: 1
Initializing random number generator from current time


Extra file open flags: (none)
128 files, 120MiB each
15GiB total file size
Block size 16KiB
Number of IO requests: 0
Read/Write ratio for combined random IO test: 1.50
Periodic FSYNC enabled, calling fsync() each 100 requests.
Calling fsync() at the end of test, Enabled.
Using synchronous I/O mode
Doing random r/w test
Initializing worker threads...

Threads started!


File operations:
    reads/s:                      3475.24
    writes/s:                     2316.83
    fsyncs/s:                     7414.17

Throughput:
    read, MiB/s:                  54.30
    written, MiB/s:               36.20

General statistics:
    total time:                          300.0116s
    total number of events:              3961928

Latency (ms):
         min:                                    0.00
         avg:                                    0.07
         max:                                   64.97
         95th percentile:                        0.15
         sum:                               296914.23

Threads fairness:
    events (avg/stddev):           3961928.0000/0.00
    execution time (avg/stddev):   296.9142/0.00

</pre>

<pre>
 tinyos@minskangui-iMac  ~  sysbench fileio --file-total-size=15G --file-test-mode=rndrw --time=300 --max-requests=0 run

sysbench 1.0.20 (using bundled LuaJIT 2.1.0-beta2)

Running the test with following options:
Number of threads: 1
Initializing random number generator from current time


Extra file open flags: (none)
128 files, 120MiB each
15GiB total file size
Block size 16KiB
Number of IO requests: 0
Read/Write ratio for combined random IO test: 1.50
Periodic FSYNC enabled, calling fsync() each 100 requests.
Calling fsync() at the end of test, Enabled.
Using synchronous I/O mode
Doing random r/w test
Initializing worker threads...

Threads started!


File operations:
    reads/s:                      92.86
    writes/s:                     61.90
    fsyncs/s:                     198.39

Throughput:
    read, MiB/s:                  1.45
    written, MiB/s:               0.97

General statistics:
    total time:                          300.0092s
    total number of events:              105823

Latency (ms):
         min:                                    0.00
         avg:                                    2.83
         max:                                  450.47
         95th percentile:                       10.84
         sum:                               299789.49

Threads fairness:
    events (avg/stddev):           105823.0000/0.00
    execution time (avg/stddev):   299.7895/0.00
</pre>



