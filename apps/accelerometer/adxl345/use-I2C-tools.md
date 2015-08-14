# use I2C tools

### check the I2c connection device

<pre>sudo i2cdetect -y 1</pre>
- 1 is Raspberry pi B+/2 (If use raspberry 1, use 0)

### Read 0x40 register
<pre>sudo i2cget -y 1 0x40</pre>

### Write 0x40 register set value '0xe3'
<pre>sudo i2cset -y 1 0x40 0xe3</pre>
