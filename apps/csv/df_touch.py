
# -*- coding: utf-8 -*-
#Author : https://github.com/jeonghoonkang

#import text as txt
import pandas as pd
import pickle
import datetime
import sys

def printProgressBar(iteration, total, prefix = 'Progress', suffix = 'Complete',\
                      decimals = 1, length = 50, fill = '█'): 
    # 작업의 진행상황을 표시
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + '-' * (length - filledLength)
    print('\r%s |%s| %s%% %s' %(prefix, bar, percent, suffix), end='\r')
    sys.stdout.flush()
    if iteration == total:
        print("...done")

def _dataframe_print_(_d):
    print (_d.head(10))
    print (_d.sample(20))    
    print (_d.tail(10))


def calc_lines(df):
    under_df = df.query(' data_occurrence_time < 20210000000000000').reset_index()
    over_df = df.query(' data_occurrence_time > 20210000000000000').reset_index()
    #print (new_df.head(50))
    print ("Dataframe 라인갯수 of under", len(under_df.index))
    print ("Dataframe 라인갯수 of over ", len(over_df.index))

def _to_unixtime(v):
    _timestring = str(v)
    #print(_timestring)
    _date = datetime.datetime.strptime(_timestring, "%Y%m%d%H%M%S%f")
    _ts = datetime.datetime.timestamp(_date)
    _ts *= 1000
    _ts = int(_ts)
    #print ("_ts type", type(_ts))
    return _ts
    

def change_time_to_unix(df):
    #over_df = df.query(' data_occurrence_time > 20210000000000000').reset_index()
    # for idx=0 in len(over_df.index) :
    _end = len(df.index)
    for idx in range(0,_end) :
        printProgressBar(idx, _end)
        _v = df.at[idx,'data_occurrence_time']
        if _v > 20210000000000000 :
            #print (df.loc[[idx],['data_occurrence_time']])
            #print (type(_v))
            df[idx, 'data_occurrence_time' ] = _to_unixtime(_v)
        else :
            df[idx, 'data_occurrence_time' ] = int(_v)    
    return df    
        

if __name__== "__main__" :

    _fname_ = '_o_df.pkl'
    df = pd.read_pickle(_fname_)
    calc_lines(df)

    df = change_time_to_unix(df)
    
    _dataframe_print_(df)


    #print (df.head(10))



    


#    temp = pickle.load(f)
#    f.close() 

    # https://towardsdatascience.com/7-different-ways-to-filter-pandas-dataframes-9e139888382a
    # df[df['population'] > 10][:5]
    # df = pd.read_pickle("df.pkl")
    # f = open("df.pkl", "rb")
    # temp = pickle.load(f)
    # f.close() 

"""     df.sort_values(by='median_income', ascending=False)[:5]
    df.query('5000 < total_rooms < 5500')[:5]
    df.sample(frac=0.01)
    df.iloc[50:55, :], df.iloc[50:55, :3]
    df_new = df.query('total_rooms > 5500').reset_index()
    df_new.head() 
            _v = df.loc[[idx],['data_occurrence_time']]
        print (_v)
        print (type(_v))
    2020-01-01 12:00:00.00 = '%Y-%m-%d %H:%M:%S.%f'
    2020-01-01 12:00:00 = '%Y-%m-%d %H:%M:%S'
    20200101120000 = '%Y%m%d%H%M%S'
    20210000000000000
    date_string = "11/22/2019"
    date = datetime.datetime.strptime(date_string, "%m/%d/%Y")
    timestamp = datetime.datetime.timestamp(date)
    """



