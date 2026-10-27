"""Convert daily CSVs into mmap NPY, recording continuous time segments.
Strictly requires timestamp column, regular cadence and unique increasing timestamps.
"""
import argparse,csv,json,datetime
from pathlib import Path
import numpy as np

def parse_time(s):
    try: return datetime.datetime.fromisoformat(s.strip().replace('Z','+00:00'))
    except Exception as e: raise ValueError(f'invalid ISO timestamp: {s!r}') from e

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input-dir',required=True)
    p.add_argument('--pattern',default='*.csv')
    p.add_argument('--output',required=True)
    p.add_argument('--timestamp',default='Timestamp')
    p.add_argument('--columns',nargs='+')
    p.add_argument('--interval-seconds',type=float,required=True,help='Expected sensor sample period, e.g. 1 or 0.1')
    p.add_argument('--encoding',default='utf-8-sig')
    p.add_argument('--delimiter',default=',')
    a=p.parse_args()
    if a.interval_seconds<=0: raise ValueError('interval must be positive')
    paths=sorted(Path(a.input_dir).rglob(a.pattern))
    if not paths: raise ValueError('No CSVs found')
    with paths[0].open(encoding=a.encoding,newline='') as f: names=csv.DictReader(f,delimiter=a.delimiter).fieldnames
    if not names or a.timestamp not in names: raise ValueError('Timestamp column missing')
    cols=a.columns or [c for c in names if c!=a.timestamp]
    if not cols or len(set(cols))!=len(cols): raise ValueError('Invalid columns')
    counts=[]; bounds=[]
    for path in paths:
        count=0; first=last=None
        with path.open(encoding=a.encoding,newline='') as f:
            reader=csv.DictReader(f,delimiter=a.delimiter)
            if not reader.fieldnames or any(c not in reader.fieldnames for c in [a.timestamp]+cols): raise ValueError(f'Missing columns: {path}')
            for lineno,row in enumerate(reader,2):
                if not any(v for v in row.values()):continue
                t=parse_time(row[a.timestamp]); first=t if first is None else first;last=t;count+=1
        if count: counts.append(count);bounds.append((first,last,path))
    if not counts: raise ValueError('No data rows')
    order=sorted(range(len(counts)),key=lambda i:bounds[i][0]);counts=[counts[i] for i in order];bounds=[bounds[i] for i in order]
    output=Path(a.output);output.parent.mkdir(parents=True,exist_ok=True)
    arr=np.lib.format.open_memmap(output,mode='w+',dtype='float32',shape=(sum(counts),len(cols)))
    segments=[];offset=0;previous=None;tol=max(1e-6,a.interval_seconds*0.001)
    for expected,(first,last,path) in zip(counts,bounds):
        written=0
        with path.open(encoding=a.encoding,newline='') as f:
            for lineno,row in enumerate(csv.DictReader(f,delimiter=a.delimiter),2):
                if not any(v for v in row.values()):continue
                try:
                    t=parse_time(row[a.timestamp]); values=np.asarray([float(row[c]) for c in cols],dtype='float32')
                    if not np.isfinite(values).all():raise ValueError('non-finite reading')
                    if previous is not None:
                        delta=(t-previous).total_seconds()
                        if delta<=0:raise ValueError(f'duplicate/out-of-order timestamp {t}, previous {previous}')
                        if abs(delta-a.interval_seconds)>tol:segments.append({'start':offset,'end':offset,'gap_seconds':delta})
                    arr[offset]=values;offset+=1;written+=1;previous=t
                except Exception as e:raise ValueError(f'{path}:{lineno}: {e}') from e
        if written!=expected:raise RuntimeError(f'File changed during conversion: {path}')
        print(f'{path}: {written:,} rows',flush=True)
    # Mark gap positions, turn them into non-overlapping continuous segments.
    gaps=[s['start'] for s in segments]; starts=[0]+gaps;ends=gaps+[offset]
    continuous=[{'start':s,'end':e} for s,e in zip(starts,ends) if e>s]
    arr.flush()
    meta={'columns':cols,'shape':[offset,len(cols)],'dtype':'float32','segments':continuous,'gap_indices':gaps,'sample_interval_seconds':a.interval_seconds,'timestamp_column':a.timestamp,'files':[str(x[2]) for x in bounds]}
    output.with_suffix('.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Wrote {output}: {offset:,} rows, {len(continuous)} continuous segments')
if __name__=='__main__':main()
