cnt = 0
xx = []
yy = []

from matplotlib import pyplot as plt
#plt.figure(figsize=(15,5))

for x in range(0,1025,1) :
    for y in range(1, 11, 1):         
        if 2**y < x :
            cnt += 1
            xx.append(x)
            yy.append(y)

print x, y, cnt    
    
#print set(xx), set(yy)

plt.plot(xx, yy, '.')
plt.show()
