# 🚀 Nexus Project Cheatsheet

## 📁 1. Aktywacja środowiska

```powershell
cd D:\nexus
.\nexus_env\Scripts\Activate.ps1
pip install -r requirements.txt

🧠 2. Sprawdzenie środowiska
where python
python --version
pip list
🤖 3. Ollama setup
# sprawdzenie instalacji
ollama list

# pobranie modelu (jeśli brak)
ollama pull phi3
ollama run phi3


Screenshot
$excludeDirs = @("venv", "nexus_env", "__pycache__", ".git", ".idea", ".vscode", "node_modules")
$root = Get-Location

Get-ChildItem -Recurse -File -Filter "*.py" |
Where-Object {
    $path = $_.FullName.ToLower()
    -not ($excludeDirs | Where-Object { $path -match $_ })
} |
ForEach-Object {

    Add-Content kod_py.txt "`n===================="
    Add-Content kod_py.txt "FILE: $($_.FullName.Replace($root, '.'))"
    Add-Content kod_py.txt "====================`n"

    Get-Content $_.FullName -Raw |
    Add-Content kod_py.txt
}




🔁 4. Standardowy workflow Git
git status
git add .
git commit -m "Opis zmian"
git push
🧾 5. Zalecane commit messages

✔ feature:

Dodano moduł przetwarzania danych

✔ fix:

Naprawiono błąd parsowania JSON

✔ refactor:

Refaktoryzacja systemu logowania
🔍 6. Debug Git (gdy coś nie działa)
git log --oneline --graph
git diff
git status
⚙️ 7. Pierwsze uruchomienie projektu
cd D:\nexus
.\nexus_env\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
🧹 8. Bezpieczny .gitignore
nexus_env/
__pycache__/
*.pyc
.env
logs/
data/
🚀 9. Full workflow (1 klik mentalnie)
Aktywuj env
Zmieniasz kod
git add .
git commit -m "..."
git push

---

# 💡 BONUS (ważne)

Jeśli chcesz, możesz sobie zrobić alias w PowerShell:

```powershell
function gsync {
    git add .
    git commit -m "update"
    git push
}

👉 potem tylko:

gsync
