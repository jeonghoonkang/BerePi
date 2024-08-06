import torch
import torch.nn as nn
import torch.optim as optim
import time

# Define a simple CNN model
class SimpleCNN(nn.Module):
    def __init__(self):
        super(SimpleCNN, self).__init__()
        self.conv1 = nn.Conv2d(3, 16, 3, 1)
        self.conv2 = nn.Conv2d(16, 32, 3, 1)
        self.conv3 = nn.Conv2d(32, 64, 3, 1)
        self.fc1 = nn.Linear(64*6*6, 128)
        self.fc2 = nn.Linear(128, 10)

    def forward(self, x):
        x = self.conv1(x)
        x = torch.relu(x)
        x = torch.max_pool2d(x, 2)
        x = self.conv2(x)
        x = torch.relu(x)
        x = torch.max_pool2d(x, 2)
        x = self.conv3(x)
        x = torch.relu(x)
        x = torch.max_pool2d(x, 2)
        x = torch.flatten(x, 1)
        x = self.fc1(x)
        x = torch.relu(x)
        x = self.fc2(x)
        return x

# Function to evaluate GPU performance
def evaluate_gpu_performance(device):
    model = SimpleCNN().to(device)
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    criterion = nn.CrossEntropyLoss()

    # Generate random input data
    inputs = torch.randn(64, 3, 32, 32).to(device)
    targets = torch.randint(0, 10, (64,)).to(device)

    # Warm up GPU
    for _ in range(10):
        outputs = model(inputs)
        loss = criterion(outputs, targets)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

    # Measure time for forward and backward pass
    start_time = time.time()
    for _ in range(100):
        outputs = model(inputs)
        loss = criterion(outputs, targets)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
    end_time = time.time()

    elapsed_time = end_time - start_time
    print(f"Elapsed time for 100 iterations: {elapsed_time:.2f} seconds")

# Check if GPU is available and run the evaluation
if __name__ == "__main__":
    if torch.cuda.is_available():
        device = torch.device("cuda")
        print("Running on GPU")
    else:
        device = torch.device("cpu")
        print("Running on CPU")

    evaluate_gpu_performance(device)
