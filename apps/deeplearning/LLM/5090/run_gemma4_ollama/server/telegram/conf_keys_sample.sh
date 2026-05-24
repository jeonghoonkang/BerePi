#!/bin/bash 
#
ENV_VARS=(
"TELEGRAM_BOT_TOKEN=***" \
"LLM_API_URL=http://127.0.0.1:8082/api/generate" \
"GEMMA4_USER_ID=***" \
"GEMMA4_PASSWORD=***" 
)

VAR_NAMES=("TELEGRAM_BOT_TOKEN" "GEMMA4_USER_ID" "GEMMA4_PASSWORD" "LLM_API_URL")
echo "$VAR_NAMES[@]"

if [ "$1" == "unset" ]; then
	for var in "${VAR_NAMES[@]}"; do
		unset "$var"
		echo $var
	done
	echo " ... has been unset "
else 
	for item in "${ENV_VARS[@]}"; do
		export "$item"
		echo $itme
	done
	echo " ... has been export, set"
fi


