# Publishing to GitHub

Run these commands from the project root after reviewing the files.

## Install GitHub CLI if needed

```powershell
winget install --id GitHub.cli
```

Close and reopen PowerShell, then authenticate:

```powershell
gh auth login
```

Choose `GitHub.com`, `HTTPS`, and browser authentication.

## Create the repository and push v0.1

```powershell
git init
git branch -M main
git add .
git status --short
git commit -m "Release CrashJarvis v0.1"
gh repo create CrashJarvis --public --source . --remote origin --push `
  --description "Local voice AI desktop agent for Windows"
git tag -a v0.1.0 -m "CrashJarvis v0.1.0"
git push origin v0.1.0
```

## Publish the Windows build

After `scripts/build.ps1` completes and the extracted ZIP is tested:

```powershell
gh release create v0.1.0 `
  .\dist\CrashJarvis-v0.1.0-windows-x64.zip `
  --title "CrashJarvis v0.1.0" `
  --notes "First public prototype of CrashJarvis for Windows. Requires an NVIDIA GPU and Ollama with qwen3.5:4b."
```

GitHub rejects individual release files larger than 2 GiB. If the archive is
larger, do not upload the ASR model cache inside the build; publish the source
and setup instructions, or distribute the full build through another service.
