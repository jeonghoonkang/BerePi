# 🧠 Deep Learning Foundations & Semiconductor FDC Analysis Guide

[![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)](https://pytorch.org/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org/)
[![Semiconductor](https://img.shields.io/badge/Semiconductor-FDC-00599C?style=for-the-badge&logo=intel&logoColor=white)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

> 딥러닝 신경망의 기본 학습 메커니즘부터 모델 용량(Capacity) 한계, 그리고 **Sine Wave vs 반도체 FDC 공정 데이터(200개 파라미터) vs LLM의 복잡도 비교 및 실무 적용 지침**을 정리한 기술 문서입니다.

---

## 📑 목차 (Table of Contents)
- [1. 신경망 '학습'의 본질과 핵심 파이프라인](#1-신경망-학습의-본질과-핵심-파이프라인)
- [2. 한정된 층수와 뉴런의 학습 한계 (Depth vs Width)](#2-한정된-층수와-뉴런의-학습-한계-depth-vs-width)
- [3. PyTorch 골든 학습 루프 표준 코드](#3-pytorch-골든-학습-루프-표준-코드)
- [4. 데이터 복잡도 3자 비교 (Sine vs FDC vs LLM)](#4-데이터-복잡도-3자-비교-sine-vs-fdc-vs-llm)
- [5. 반도체 FDC 장비 데이터 실무 가이드](#5-반도체-fdc-장비-데이터-실무-가이드)
- [6. 소형 모델 최적화를 위한 4대 실전 수칙](#6-소형-모델-최적화를-위한-4대-실전-수칙)

---

## 1. 신경망 '학습'의 본질과 핵심 파이프라인

신경망이 '배운다'는 것은 오차(Loss)를 줄이기 위해 내부의 수많은 가중치($W$, Weight)를 정교하게 갱신해 나가는 과정입니다.


| 모듈 | 수식 / 공식 | 핵심 역할 및 엔지니어링 특징 |
| :--- | :--- | :--- |
| **Tensor** | `Shape: [Batch, Features]` | 고차원 기하학 공간 속 점들의 다차원 배열 (CPU/GPU 병렬 연산) |
| **Linear Layer** | $Y = XW^T + b$ | 좌표 공간을 회전, 확대, 축소하는 아핀(Affine) 사영 변환 |
| **ReLU** | $f(x) = \max(0, x)$ | 공간을 꺾는 경첩(Hinge)을 생성하여 XOR 등 비선형 곡면 형성 및 기울기 소실 방지 |
| **Softmax** | $P(y_i) = \frac{e^{z_i - \max(z)}}{\sum e^{z_j - \max(z)}}$ | 로짓을 확률(합 1.0)로 변환. **최댓값 빼기 트릭**으로 부동소수점 오버플로우 원천 차단 |
| **Cross-Entropy** | $\text{Loss} = -\log(P_{\text{정답}})$ | 예측 확률과 실제 라벨 간의 쿨백-라이블러(KL) 발산 거리 측정 및 벌점 부여 |
| **Autograd** | $\frac{\partial \text{Loss}}{\partial W} = \prod \text{Local Gradients}$ | 계산 그래프를 역추적하며 연쇄 법칙(Chain Rule)으로 각 파라미터 미분값 자동 계산 |
| **Adam** | $W \leftarrow W - \eta \frac{\hat{m}}{\sqrt{\hat{v}} + \epsilon}$ | **1차 모멘텀(관성 방향)** + **2차 모멘텀(적응형 보폭)** 결합으로 최적점 고속 수렴 |

---

## 2. 한정된 층수와 뉴런의 학습 한계 (Depth vs Width)

> [!IMPORTANT]
> **보편 근사 정리(Universal Approximation Theorem)의 역설**  
> *"1개 은닉층으로도 모든 연속 함수를 근사할 수 있다"*는 이론은 뉴런 수가 **무한대($\infty$)**에 가까울 때만 유효합니다. 실제 제한된 뉴런 환경에서는 얕은 신경망이 쉽게 언더피팅(Underfitting)에 빠집니다.

### 📐 너비(Width)보다 깊이(Depth)가 지수적으로 우수한 이유
신경망의 층(Depth)을 쌓는 행위는 **종이를 반으로 거듭 접는 행위**와 같습니다.

* **너비만 늘린 1개 층:** 선형 영역 분할이 뉴런 수 $N$에 비례 ($O(N)$ 선형 증가)
* **깊이를 늘린 $L$개 층:** 층을 거칠 때마다 공간이 반복해서 접혀 **$O(N^L)$ 지수적(Exponential) 영역 분할** 달성

따라서 총 뉴런 예산이 제한되어 있다면 **`[1개 층 × 128 뉴런]`보다 `[3개 층 × 32 뉴런]`이 훨씬 복잡하고 정교한 비선형 결정 경계**를 형성합니다.

---

## 3. PyTorch 골든 학습 루프 표준 코드

아래 코드는 비선형 난제인 XOR 문제를 100% 분류하는 표준 PyTorch 템플릿입니다.

```python
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

# 1. 디바이스 및 데이터 준비
device = torch.device("mps" if torch.backends.mps.is_available() else 
                      "cuda" if torch.cuda.is_available() else "cpu")
X = torch.tensor([[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0]], dtype=torch.float32)
y = torch.tensor([0, 1, 1, 0], dtype=torch.int64)

loader = DataLoader(TensorDataset(X, y), batch_size=2, shuffle=True)

# 2. 모델 아키텍처 정의
class Net(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear(2, 16)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(p=0.1)
        self.fc2 = nn.Linear(16, 2)

    def forward(self, x):
        return self.fc2(self.dropout(self.relu(self.fc1(x))))

model = Net().to(device)
criterion = nn.CrossEntropyLoss() # 내부 수치안정 Softmax + CrossEntropy 자동 내장
optimizer = optim.Adam(model.parameters(), lr=0.05)

# 3. 골든 5단계 학습 루프
for epoch in range(1, 201):
    model.train() # 드롭아웃 활성화
    for x_batch, y_batch in loader:
        x_b, y_b = x_batch.to(device), y_batch.to(device)
        
        optimizer.zero_grad()         # 1. 기울기 초기화
        out = model(x_b)              # 2. 순전파
        loss = criterion(out, y_b)    # 3. 손실 계산
        loss.backward()               # 4. 역전파 자동 미분
        optimizer.step()              # 5. Adam 가중치 갱신




##4. 반도체 장비 FDC에 딥러닝 적용 실무 가이드
핵심 결론: 반도체 FDC는 LLM 같은 거대 모델이 전혀 필요하지 않으며, 데이터의 저장 형태(스냅샷 테이블 vs 원시 시계열 파형)에 따라 최적의 알고리즘이 명확히 나뉩니다.
상황 A. 스텝별 요약 통계량 CSV인 경우 👉 [XGBoost / LightGBM 적극 추천]
각 공정 스텝의 평균(Mean), 표준편차(Std), 최댓값(Max), 최솟값(Min) 등으로 요약된 테이블 데이터라면 딥러닝보다 트리 앙상블 모델이 훨씬 우수합니다.

장점:

학습 속도가 딥러닝 대비 100배 이상 빠름.

결측치 및 이상치(Spike Noise)에 강인함.

설명 가능성(XAI): SHAP 및 Feature Importance를 통해 **"200개 센서 중 몇 번 센서가 불량의 주원인인가"**를 공정 엔지니어에게 명확하게 시각적으로 제시 가능.

상황 B. 0.1초 단위 원시 파형 시계열(Raw Trace)인 경우 👉 [경량 딥러닝 추천]
1장의 웨이퍼 가공 시간 동안 200개 센서가 뿜어내는 수천 줄의 파형(Waveform) 전체를 분석해야 할 때는 딥러닝이 필수적입니다.

추천 모델:

1D-CNN: 200개 센서 파형에서 미세한 아크(Arcing, 순간 스파크)나 이상 패턴을 이미지 필터처럼 초고속 탐지.

오토인코더(Autoencoder - 비지도 학습): 정상 웨이퍼 파형만 학습한 후, 불량 발생 시 복원 오차(Reconstruction Error) 급증을 감지 (0.1% 미만의 극단적인 불량 데이터 불균형 문제 해결).

시계열 트랜스포머 (PatchTST, Informer): 센서들 사이의 시간적 선후 인과관계를 학습하여 장비 고장을 수 시간 전에 사전 예지보전(PdM).
