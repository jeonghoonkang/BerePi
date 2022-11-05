import matplotlib.pyplot as plt
import os
import time

plt.rcParams["figure.figsize"] = (20,11)


# YYYY-mm-dd HH:MM:SS -> epoch
def convertTimeToEpoch(_time):
    date_time = "%s.%s.%s %s:%s:%s" %(_time[8:10], _time[5:7], _time[:4], _time[11:13], _time[14:16], _time[17:19])
    pattern = "%d.%m.%Y %H:%M:%S"
    epoch = int (time.mktime(time.strptime(date_time, pattern)))
    return epoch
    
    
def draw_chart(tdf, _numeric, time_field, start_dt, end_dt):
    try:
        start_dt = convertTimeToEpoch(start_dt) * 1000.0
        end_dt = convertTimeToEpoch(end_dt) * 1000.0
        print(start_dt)
        print(end_dt)
        tdf = tdf[tdf[time_field] >= start_dt]
        tdf = tdf[tdf[time_field] <= end_dt]
        print(tdf)
    except:
        print("time format error")
        None
    
    fig, ax = plt.subplots()
    for col in _numeric:
        ax.plot(tdf[time_field], tdf[col],
            linestyle='none', 
            marker='o', 
            markersize=5,
            label=col,
            alpha=0.5)
        ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.05),
                fancybox=True, shadow=True, ncol=3, fontsize=25) ## 범례
    plt.xlabel('time', fontsize=25)
    plt.ylabel('value', fontsize=25)
    if not os.path.isdir('static/output'):
        os.makedirs('static/output')
    plt.savefig('./static/output/output.png')
    print('saved ./static/output/output.png')
    return './static/output/output.png'