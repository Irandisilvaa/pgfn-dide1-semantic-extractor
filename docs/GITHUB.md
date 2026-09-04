# Subir para GitHub no Windows

Use repositório privado/institucional autorizado.

No PowerShell:

```powershell
git init
git add .
git status
```

Confirme que não aparecem para commit:

```text
.env
runtime\
*.gguf
.venv\
```

Depois:

```powershell
git commit -m "feat: PGFN DIDE1 semantic extractor v1.0.1 Windows"
git branch -M main
git remote add origin git@github.com:ORGANIZACAO/REPOSITORIO.git
git push -u origin main
```

Nunca versionar token, decisões, recortes reais ou GGUF.
