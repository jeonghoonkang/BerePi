# Author: Jeonghhoon Kang (https://github.com/jeonghoonkang)
# source sine/bin/activate # deactivate 
# python3 sine_wave.py

import numpy as np
print(np.__version__)

import matplotlib.pyplot as plt

# x values from 0 to 2*pi
x = np.linspace(0, 2 * np.pi, 100)
# y values as sine of x
y = np.sin(x)


print ("sine 0 (0) is almost zero             ", np.sin(0))
print ("sine pi/3 (30) is 1 / 2               ", np.sin(np.pi/6))
print ("sine pi/3 (60) is almost sq root 2 /2 ", np.sin(np.pi/3))
print ("sine pi/2 (90) is almost one, 1       ", np.sin(np.pi/2))
print ("sine 4*pi/6 (120) is sq root 2 /2     ", np.sin(2*np.pi/3))
print ("sine 5*pi/6 (150) is       1/2        ", np.sin(5*np.pi/6))
print ("sine pi (180) is almost zero           ", np.sin(np.pi))


# Create the plot
plt.plot(x, y)

# Add title and labels
plt.title('Sine Wave')
plt.xlabel('x values')
plt.ylabel('sin(x)')

# Show the plot
# plt.show()
# Save the plot as a PNG file
# plt.savefig('/Users/tinyos/devel/BerePi/apps/school_math/sine_wave.png')