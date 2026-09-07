# B-rep CAD geometry + topology 학습 예제

이 예제는 CAD를 mesh나 voxel로 변환하지 않고 OpenCascade의 **B-rep face와 edge를 직접 사용**합니다. 각 face에서 곡면 geometry를 읽고, face를 node로 공유 edge를 graph edge로 만든 뒤 하나의 금형/부품을 분류합니다.

## 무엇을 학습하는가

- Face geometry: trimmed UV grid 위의 3D 좌표, 바깥쪽 단위 법선, Gaussian/mean curvature, trim 유효 mask
- Face 속성: 면적, 전체 대비 면적, parameter span, plane/cylinder/cone/sphere/torus/Bezier/B-spline 종류, rational/periodic 여부
- Topology: 하나의 B-rep edge를 공유하는 두 face의 adjacency
- Edge geometry: edge 길이, curve 종류, dihedral cosine/sine, convex/concave/smooth 여부, closed 여부
- 전체 형상: face CNN embedding을 edge-aware graph message passing으로 전파한 뒤 mean/max graph pooling

따라서 tessellation 품질에 좌우되는 mesh 학습과 달리 원래 CAD의 곡면 및 위상 정보를 보존합니다. 입력 크기와 원점은 정규화되고 곡률도 같은 비율로 보정되므로, mm 또는 inch 등 단위가 다른 일반 금형 파일을 함께 다루기 쉽습니다.

## 설치

`pythonocc-core`는 PyPI보다 conda-forge 설치가 안정적입니다.

```bash
cd E:/devel/BerePi/apps/deeplearning/models/3dcad
conda env create -f environment.yml
conda activate brep-cad-learning
```

지원 형식은 `.step`, `.stp`, `.iges`, `.igs`, `.brep`, `.brp`입니다. IGES는 원본에 topology가 약하거나 surface가 분리되어 있을 수 있으므로 가능하면 STEP을 권장합니다.

## 데이터 구성과 실행

원본의 하위 폴더 구조는 유지됩니다.

```text
data/raw/
  core/core_001.step
  cavity/cavity_001.step
  slider/slider_001.step
```

1. 특징을 한 번 추출하여 압축 NPZ로 cache합니다.

```bash
python -m brep_learning.extract data/raw data/processed --resolution 10
```

처리에 실패한 CAD가 있더라도 batch 전체를 계속 진행하며 `data/processed/failures.csv`에 원인을 기록합니다. 일반 금형에서 자주 보이는 자유곡면은 B-spline으로 처리됩니다.

2. 라벨 manifest를 만들고 `label` 열을 실제 class ID(`0..num_classes-1`)로 수정합니다.

```bash
python make_labels.py data/raw data/labels.csv
```

```csv
file,label
core/core_001.step,0
cavity/cavity_001.step,1
slider/slider_001.step,2
```

3. `config.yaml`의 `num_classes` 및 경로를 확인하고 학습합니다.

```bash
python train.py --config config.yaml
python predict.py data/raw/core/core_002.step runs/mold_classifier/best.pt --resolution 10
```

학습 결과는 `best.pt`와 `history.json`으로 저장됩니다. 추론의 `--resolution`은 학습용 특징 추출 해상도와 같게 사용하는 것이 좋습니다.

## 실제 금형 데이터 적용 시 권장 사항

- CAD healing/sewing 후 하나의 solid 또는 shell로 내보내면 adjacency가 더 정확합니다.
- 동일 제품의 설계 revision이 train/validation에 동시에 들어가지 않도록 제품군 단위로 split하십시오. 현재 예제는 재현 가능한 무작위 split이므로 운영 데이터에서는 manifest에 split 열을 추가하는 방식이 좋습니다.
- class 불균형이 심하면 `CrossEntropyLoss(weight=...)` 또는 weighted sampler를 적용하십시오.
- 매우 작은 fillet face가 많은 금형은 face 수가 크게 늘어납니다. 먼저 그대로 학습해 보고 GPU 메모리가 부족할 때만 작은 면 제거/graph pooling을 고려하십시오.
- shape classification이 아니라 face별 가공 특징(포켓, 홀, 파팅면 등)을 검출하려면 `model.py`의 graph pooling 이전 face embedding에 node classifier를 연결하고 face label을 준비하면 됩니다.

## 검증

CAD kernel 없이도 모델/graph tensor의 동작을 확인할 수 있습니다.

```bash
python -m pytest tests -q
```

주의: 이 코드는 교육 및 확장용 기준 구현입니다. 산업용 대규모 데이터에는 OpenCascade process 병렬화, invalid shape healing, class/split 관리, feature cache versioning을 추가하는 것을 권장합니다.
