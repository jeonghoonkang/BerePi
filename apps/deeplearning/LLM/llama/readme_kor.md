# FSDP를 이용한 LLaMA 파인튜닝 예제

이 폴더에는 PyTorch의 **FSDP**(Fully Sharded Data Parallel) 기능을 사용하여 LLaMA 모델을 학습하는 스크립트가 들어 있습니다.

## 필요 패키지

파인튜닝을 위해서는 PyTorch, Transformers, Datasets 패키지가 필요하며 PyTorch는 분산 기능이 활성화된 빌드여야 합니다.

```bash
pip install torch transformers datasets
```

## Wikitext 데이터셋 예제

`finetune_fsdp.py` 스크립트는 wikitext 데이터셋 일부를 사용해 두 개의 GPU에서 모델을 학습합니다.

```bash
torchrun --nproc_per_node=2 finetune_fsdp.py --model meta-llama/Llama-2-7b-hf
```

## 사용자 데이터로 학습하기

`finetune_fsdp_custom.py`를 실행하면 준비한 텍스트 파일을 이용해 모델을 파인튜닝할 수 있습니다. 여러 파일은 쉼표로 구분하여 입력합니다.

```bash
torchrun --nproc_per_node=2 finetune_fsdp_custom.py \
    --model meta-llama/Llama-2-7b-hf \
    --data_files example1.txt,example2.txt
```

스크립트는 지정된 텍스트 파일을 로드해 토크나이즈한 뒤 FSDP 모드로 학습을 수행합니다. `--output_dir`와 `--max_steps` 옵션을 사용해 체크포인트 저장 위치와 학습 스텝 수를 조절할 수 있습니다.

## 직접 FSDP 루프 사용하기

`finetune_fsdp_manual.py` 스크립트는 파이토치의 FSDP API를 이용해 간단한 학습 루프를 구성한 예제입니다. 두 개 이상의 GPU에서 다음과 같이 실행합니다.

```bash
torchrun --nproc_per_node=2 finetune_fsdp_manual.py \
    --model meta-llama/Llama-2-7b-hf \
    --data_files mydata.txt --epochs 1
```

이 예제는 `torch.distributed`를 초기화한 뒤 모델을 `FullyShardedDataParallel` 로 감싸고, 입력 텍스트를 토큰화하여 기본적인 학습 루프를 수행합니다.

