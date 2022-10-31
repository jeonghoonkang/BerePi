import pandas as pd 
from prophet import Prophet 

df = pd.read_csv('https://raw.githubusercontent.com/facebook/prophet/master/examples/example_wp_log_peyton_manning.csv')
df['y'] = df['y'].apply(lambda x: x + 1)
print (df.head())
