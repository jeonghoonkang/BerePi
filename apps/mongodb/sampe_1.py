import pandas as pd
import bson

FILE="/folder/file.bson"

with open(FILE,'rb') as f:
    data = bson.decode_all(f.read())

main_df=pd.DataFrame(data)
main_df.describe()
