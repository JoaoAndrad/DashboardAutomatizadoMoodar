# DV Admin Automator

Mini skeleton for automating Django Admin using Selenium.

## Getting started

1. Create a virtualenv and install deps:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Run the CLI (example):

```powershell
python -m dv_admin_automator.cli run path\to\config.yaml
```

## Activation (first-run)

To run the activation flow against the default activation service:

```powershell
python -m dv_admin_automator.cli activate
```

Or specify the activation domain explicitly:

```powershell
python -m dv_admin_automator.cli activate https://moodar-activation.squareweb.app
```

## Notes

- This is an initial skeleton. Browser requires Chrome installed. Chromedriver will be auto-downloaded.
- Next: implement page objects, steps and richer reporting.
