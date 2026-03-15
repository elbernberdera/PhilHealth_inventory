# PhilHealth Inventory

A Django-based inventory application for managing PhilHealth-related data.

## 🧰 Project Setup

### 1) Create and activate the virtual environment

From the project root (`C:\Users\elber\Desktop\Inventory`):

```sh
python -m venv my_env
```

Then activate the venv for your shell:

- **Windows Command Prompt (cmd.exe):**
  ```bat
  my_env\Scripts\activate.bat
  ```
- **PowerShell:**
  ```powershell
  .\my_env\Scripts\Activate.ps1
  ```
- **Git Bash / WSL / macOS / Linux:**
  ```sh
  source my_env/bin/activate
  ```

> If you already created the venv, just activate it (no need to recreate).

### 2) Install dependencies

```powershell
cd .\PhilHealth_inventory
python -m pip install -r requirements.txt
```

### 3) Apply database migrations

```powershell
python manage.py migrate
```

### 4) Run the development server

```powershell
python manage.py runserver
```

Then visit: http://127.0.0.1:8000/

---

## ✅ Versions (as of this project)

- **Python**: 3.14.x
- **Django**: 4.2.29
- **Database adapter**: mysqlclient >= 2.2.0

> If you need the exact installed versions in your environment, run:
>
> ```powershell
> python --version
> python -m pip list
> ```

---

## 📄 Project Layout

- `PhilHealth_inventory/` — Django project directory
  - `manage.py` — Django command utility
  - `philhealth_inventory/` — project settings + URLs
  - `inventory/` — main app (models, views, templates, etc.)

---

## 📝 Notes

- Make sure your database settings in `PhilHealth_inventory/philhealth_inventory/settings.py` match your local MySQL credentials.
- If you add new dependencies, update `requirements.txt` and run:
  ```powershell
  python -m pip install -r requirements.txt
  ```
