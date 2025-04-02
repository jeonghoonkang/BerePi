
https://www.llama.com/llama-downloads/

How to download the model
Visit the Llama repository in GitHub where instructions can be found in the Llama README.

1
Install the Llama CLI
In your preferred environment run the command below:
Command
pip install llama-stack
Use -U option to update llama-stack if a previous version is already installed:
Command
pip install llama-stack -U
2
Find models list
See latest available models by running the following command and determine the model ID you wish to download:
Command
llama model list
If you want older versions of models, run the command below to show all the available Llama models:
Command
llama model list --show-all
3
Select a model
Select a desired model by running:
Command
llama model download --source meta --model-id  MODEL_ID
4
Specify custom URL
Llama 3.2: 11B & 90B
When the script asks for your unique custom URL, please paste the URL below
URL
https://llama3-2-multimodal.llamameta.net/*?Policy=eyJTdGF0ZW1lbnQiOlt7InVuaXF1ZV9oYXNoIjoiM3E3eGdkcm55c3VtY3dieXRxbWN2ZmxqIiwiUmVzb3VyY2UiOiJodHRwczpcL1wvbGxhbWEzLTItbXVsdGltb2RhbC5sbGFtYW1ldGEubmV0XC8qIiwiQ29uZGl0aW9uIjp7IkRhdGVMZXNzVGhhbiI6eyJBV1M6RXBvY2hUaW1lIjoxNzQzNzI3NTI5fX19XX0_&Signature=GEC2YhOPhXery2JfZf6LU7LgvVytFNL3zrGuYYskY2tBycjY52UFk9EVKBySjTa6-ihnsjM5qIO4o5NOjETx5uWL0dfrVbEW8xN0lieINm-bZHEcBlTYmgQMrIouqw538mIMP6YYtPEynGbKBNAglh3as%7EavGmxm45D9WPhDJiTG3HG-jCwD0M2s9UZMPM8lLsPIKN1OdMnaaePIcix3wZDZtK4doXHTu69kBrZMgWR17F1MqGaterAW-QsPCh8w0LL4xKnbwqQRr0Lc8fm941NzJjuszJAl96DlYffPkxF3KzYg855ATSI4p2CVB7etXKnt4UK7A7%7EM7Bqkm%7EXVpg__&Key-Pair-Id=K15QRJLYKIFSLZ&Download-Request-ID=1798107580769777
Please save copies of the unique custom URLs provided above, they will remain valid for 48 hours to download each model up to 5 times, and requests can be submitted multiple times. An email with the download instructions will also be sent to the email address you used to request the models.

Available models
With each model size, please find:
Pretrained weights: These are base weights that can be fine-tuned, domain adapted with full flexibility.
Instruct weights: These weights are for the models that have been fine-tuned and aligned to follow instructions. They can be used as-is in chat applications or futher fine tuned and aligned for specific use cases.
Trust and safety model: Our models offer a collection of specialized models tailored to specific development needs.
Available models for download include:

Pretrained:
Llama-3.2-11B-Vision
Llama-3.2-90B-Vision
Fine-tuned:
Llama-3.2-11B-Vision-Instruct
Llama-3.2-90B-Vision-Instruct
Trust and safety models:
Llama-Guard-3-11B-Vision
Recommended tools
Code Shield
A system-level approach to safeguard tools, Code Shield adds support for inference-time filtering of insecure code produced by LLMs. This offers mitigation of insecure code suggestions risk, code interpreter abuse prevention, and secure command execution.
Now available on Github

Cybersecurity Eval
The first and most comprehensive set of open source cybersecurity safety evals for LLMs. These benchmarks are based on industry guidance and standards (e.g. CWE & MITRE ATT&CK) and built in collaboration with our security subject matter experts.
Now available on Github
