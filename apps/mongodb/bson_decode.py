
import pandas as pd
import bson

file='/home/gwangsik/machine_topic_2201.bson'

f = open(file, 'rb')

decode = bson.decode_file_iter(f)
exit(1)
main_df = pd.DataFrame(decode)

