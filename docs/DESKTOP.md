# Popy POS Desktop App

The Windows installer is one setup file. It contains the POS window, the Django server, and a private MySQL 8.4. Installing it does not add a Windows MySQL service and does not download anything else. MySQL listens on 127.0.0.1 only, on port 3307 or the next free port, never 3306.

Shop data stays in `%LOCALAPPDATA%\Popy POS`. Reinstalling the program does not delete sales. The uninstaller leaves that folder in place.

The first launch asks for the shop name and the first admin account, and creates that shop on the Pro plan. Shops already on this computer are marked Pro the next time the app starts. Later launches open the login screen.

Attendance and the other Pro features work on this computer. Email and SMS stay on the cloud version: this server does not send them, and Settings leaves those switches off. If Server settings point the window at the cloud API, that cloud shop's plan decides, including email and SMS for a Pro shop.

## Development

Development still uses the Vite server and a Django process you start yourself. It does not start the private MySQL.

1. Start Django in `popy-be`:

   ```bash
   python manage.py runserver 127.0.0.1:8000
   ```

2. Start Electron in `popy-fe`:

   ```bash
   npm run electron:dev
   ```

The dev window talks to `http://127.0.0.1:8000/api`. The Server settings screen can still point at the cloud API or another URL.

That Django process keeps the cloud rules: a shop stays Free until its plan is Pro, and email and SMS follow the plan. The packaged app uses the desktop rules instead. Start Django with `config.settings.desktop` when you need to try those rules outside the installer.

## Build the installer

On a Windows machine with Node.js and internet access:

```bash
cd popy-fe
npm run electron:build
```

That command downloads MySQL, embeddable Python, and the Visual C++ runtime into `desktop/runtime` (gitignored), copies the Django project, then builds `popy-fe/release/Popy POS Setup 1.0.0.exe`.

The setup file installs the Visual C++ 2022 runtime if the PC does not already have it, because MySQL needs it.

MySQL Community Server is GPL. The installer shows `desktop/THIRD_PARTY_NOTICES.txt`, and the MySQL license file is included under `resources\mysql\LICENSE`.
