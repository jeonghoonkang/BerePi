import pandas as pd
import os, sys
file_path = '../**.json'

def pre_process():
  #with open(file_path, 'r') as file: 
  chunks = pd.read_json(file_path, lines=True, chunksize=1000)  
  print (type(chunks))
  print (chunks)  
  for chunk in chunks: 
    print (chunk)
 
if __name__ == '__main__':  
  pre_processs()
  
 
