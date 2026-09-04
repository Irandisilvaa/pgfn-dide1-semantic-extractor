# v1.0.1 Windows

Esta release mantém o núcleo Python da v1.0 e troca a camada operacional para
Windows/PowerShell.

Inclui:
- scripts `.ps1`;
- criação de `.venv` no Windows;
- detecção de GPU via `nvidia-smi`;
- servidor `llama-server.exe`;
- caminhos Windows no `.env.example`;
- execução 10/100/500/1000;
- execução N arbitrário;
- processamento integral read-only;
- checkpoint/resume;
- verificação de binding local do `llama-server`.
