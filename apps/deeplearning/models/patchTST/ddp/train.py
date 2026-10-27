import argparse, os, random, json, bisect
import numpy as np
import torch
import torch.distributed as dist
from torch import nn
from torch.nn.parallel import DistributedDataParallel as DDP
from torch.utils.data import Dataset, DataLoader, DistributedSampler

class Windows(Dataset):
    def __init__(self, path, context, horizon, task, segments):
        self.path=path
        self.x=np.load(path,mmap_mode='r')
        assert self.x.ndim==2, 'Expected [time, channels] .npy'
        self.context=context; self.horizon=horizon; self.task=task
        needed=context+(horizon if task=='forecast' else 0)
        self.ranges=[]; self.cumulative=[]; total=0
        for start,end in segments:
            count=max(0,end-start-needed+1)
            if count:
                self.ranges.append((start,count))
                total+=count
                self.cumulative.append(total)
        if total==0: raise ValueError('No valid windows; check context/horizon and CSV lengths')
    def __len__(self): return self.cumulative[-1]
    def __getitem__(self,i):
        k=bisect.bisect_right(self.cumulative,i)
        previous=self.cumulative[k-1] if k else 0
        j=self.ranges[k][0]+(i-previous)
        x=np.array(self.x[j:j+self.context],dtype=np.float32,copy=True)
        if self.task=='forecast': y=np.array(self.x[j+self.context:j+self.context+self.horizon],dtype=np.float32,copy=True)
        else: y=x.copy()
        return torch.from_numpy(x),torch.from_numpy(y)

class PatchTST(nn.Module):
    def __init__(self,channels,context,horizon,patch,stride,d_model,heads,layers,task):
        super().__init__()
        self.channels=channels;self.patch=patch;self.stride=stride;self.task=task
        n=(context-patch)//stride+1
        self.proj=nn.Linear(patch,d_model)
        self.pos=nn.Parameter(torch.zeros(1,n,d_model))
        layer=nn.TransformerEncoderLayer(d_model,heads,dim_feedforward=d_model*4,batch_first=True,norm_first=True,dropout=.1)
        self.encoder=nn.TransformerEncoder(layer,layers,enable_nested_tensor=False)
        self.head=nn.Linear(n*d_model,horizon if task=='forecast' else context)
    def forward(self,x):
        b,t,c=x.shape
        z=x.transpose(1,2).reshape(b*c,t).unfold(-1,self.patch,self.stride)
        z=self.encoder(self.proj(z)+self.pos)
        out=self.head(z.flatten(1)).reshape(b,c,-1).transpose(1,2)
        return out

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--data',required=True);p.add_argument('--meta',help='CSV conversion JSON metadata (default: same stem as --data)');p.add_argument('--task',choices=['forecast','anomaly'],required=True)
    p.add_argument('--context',type=int,default=512);p.add_argument('--horizon',type=int,default=96)
    p.add_argument('--patch',type=int,default=16);p.add_argument('--stride',type=int,default=8)
    p.add_argument('--d-model',type=int,default=128);p.add_argument('--heads',type=int,default=4);p.add_argument('--layers',type=int,default=3)
    p.add_argument('--batch',type=int,default=32);p.add_argument('--epochs',type=int,default=10);p.add_argument('--lr',type=float,default=1e-4)
    p.add_argument('--workers',type=int,default=4);p.add_argument('--out',default='model.pt');p.add_argument('--train-ratio',type=float,default=.8)
    a=p.parse_args()
    rank=int(os.environ.get('RANK',0));world=int(os.environ.get('WORLD_SIZE',1));local=int(os.environ.get('LOCAL_RANK',0))
    distributed=world>1
    if distributed: dist.init_process_group('nccl');torch.cuda.set_device(local)
    device=torch.device(f'cuda:{local}' if torch.cuda.is_available() else 'cpu')
    torch.manual_seed(42);np.random.seed(42);random.seed(42)
    arr=np.load(a.data,mmap_mode='r');total,channels=arr.shape
    assert a.context>=a.patch and 0<a.train_ratio<1
    meta_path=a.meta or os.path.splitext(a.data)[0]+'.json'
    if os.path.exists(meta_path):
        with open(meta_path,encoding='utf-8') as f: meta=json.load(f)
        if meta['shape'] != [total,channels]: raise ValueError('Metadata shape mismatch')
        raw_segments=[(int(v['start']),int(v['end'])) for v in meta['segments']]
        if any(start<0 or end>total or end<=start for start,end in raw_segments):
            raise ValueError('Invalid metadata segment boundaries')
    else:
        raw_segments=[(0,total)]
    # Chronological global split; do not leak later dates into training.
    cutoff=int(total*a.train_ratio)
    train_segments=[(start,min(end,cutoff)) for start,end in raw_segments if start<cutoff]
    ds=Windows(a.data,a.context,a.horizon,a.task,train_segments)
    sampler=DistributedSampler(ds,num_replicas=world,rank=rank,shuffle=True) if distributed else None
    loader=DataLoader(ds,batch_size=a.batch,sampler=sampler,shuffle=sampler is None,num_workers=a.workers,pin_memory=device.type=='cuda',persistent_workers=a.workers>0)
    model=PatchTST(channels,a.context,a.horizon,a.patch,a.stride,a.d_model,a.heads,a.layers,a.task).to(device)
    if distributed:model=DDP(model,device_ids=[local])
    opt=torch.optim.AdamW(model.parameters(),lr=a.lr)
    for epoch in range(a.epochs):
        if sampler:sampler.set_epoch(epoch)
        model.train();total_loss=torch.zeros(2,device=device)
        for x,y in loader:
            x=x.to(device,non_blocking=True);y=y.to(device,non_blocking=True)
            opt.zero_grad(set_to_none=True)
            with torch.autocast(device_type=device.type,dtype=torch.bfloat16,enabled=device.type=='cuda'):
                pred=model(x);loss=(pred.float()-y).square().mean()
            loss.backward();opt.step()
            total_loss+=torch.tensor([loss.detach().item()*x.size(0),x.size(0)],device=device)
        if distributed:dist.all_reduce(total_loss)
        if rank==0:print(f'epoch {epoch+1}: train MSE={total_loss[0].item()/total_loss[1].item():.6f}',flush=True)
    if rank==0:
        raw=model.module if distributed else model
        torch.save({'state_dict':raw.state_dict(),'config':vars(a),'channels':channels},a.out)
        print('saved:',a.out)
    if distributed:dist.destroy_process_group()
if __name__=='__main__':main()
