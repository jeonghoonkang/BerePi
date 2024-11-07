## PyTorch

### Performance
#### Various system
- Average inference time per batch: 0.000357 seconds (Hailo Rpi5)
- Average inference time per batch: 0.000454 seconds (i7-desktop)
- Average inference time per batch: 0.000109 seconds (Xeon 1.4GHz)
- Average inference time per batch: 0.000257 seconds (Xeon - 2 CPU)
- Average inference time per batch: 0.000128 seconds (2way 4090)
  
### check devel environment
#### Hailo AI environment
- source ./hailo-rpi5-examples/setup_env.sh

### performance test
<pre>
import torch
import time

# 테스트용 간단한 CNN 모델 정의
class SimpleCNN(torch.nn.Module):
    def __init__(self):
        super(SimpleCNN, self).__init__()
        self.conv1 = torch.nn.Conv2d(3, 16, 3, stride=1, padding=1)
        self.pool = torch.nn.MaxPool2d(2, 2)
        self.fc1 = torch.nn.Linear(16 * 16 * 16, 10)

    def forward(self, x):
        x = self.pool(torch.nn.functional.relu(self.conv1(x)))
        x = x.view(-1, 16 * 16 * 16)
        x = self.fc1(x)
        return x

# 모델 생성 및 임의 데이터 생성
model = SimpleCNN()
dummy_input = torch.randn(1, 3, 32, 32)

# 모델 성능 테스트
start_time = time.time()
with torch.no_grad():
    for _ in range(100):
        output = model(dummy_input)
end_time = time.time()

# 평균 처리 시간 계산
avg_time = (end_time - start_time) / 100
print(f"Average inference time per batch: {avg_time:.6f} seconds")

</pre>
