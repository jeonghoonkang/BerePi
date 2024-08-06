import torch
import numpy as np
import torch.nn as nn
import torch.autograd.profiler as profiler


class ProfileTargetModule(nn.Module):
    def __init__(self, in_features: int, out_features: int, bias: bool = True, bn: bool = True):
        super(ProfileTargetModule, self).__init__()
        self.conv = nn.Conv2d(in_features, out_features, kernel_size=3, padding=1, bias=bias)
        self.bn = nn.BatchNorm2d(out_features)
        
    def forward(self, input):
        with profiler.record_function("CONV FORWARD"):
            out = self.conv(input)
            out = self.bn(out)

        with profiler.record_function("SVD"):
            u, s, vh = np.linalg.svd(out.cpu().detach().numpy())
            s = torch.from_numpy(s).cuda()
            
        return out, s



x = torch.rand(1, 3, 128, 128).cuda()
model = ProfileTargetModule(3, 8, True, True).cuda()
out, s = model(x)

with profiler.profile(with_stack=True, use_cuda=True, profile_memory=True) as prof:
    out, s = model(x)
    
print(prof.key_averages().table(sort_by="cuda_time_total", row_limit=10))
