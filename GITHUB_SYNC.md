# Sync the ERP from a private GitHub repo

This replaces copying folders around. The code lives in a **private** GitHub repo. The factory PC
gets its first copy with `git clone`, and every future update is just `git pull` (or double-click
`update.bat`). Your **data and secrets never go to GitHub** — `data.json`, `data.sqlite`,
`secrets.local.json`, and `backups/` are all gitignored, so each machine keeps its own.

The flow going forward:
```
I make a change  →  it's committed here on your dev machine
you: git push    →  it goes up to the private GitHub repo
factory PC: update.bat (git pull)  →  it comes down and the server restarts
```

---

## Part A — One-time: put the code on GitHub (from your dev machine / laptop)

1. On **github.com**, click **New repository** → name it e.g. `rel-dyeing-erp` → set **Private** →
   **Create repository** (do NOT add a README/gitignore, the repo already has them).
2. On your dev machine, in the `REL_DYEING` folder, run (replace the URL with your new repo's):
   ```
   git remote add origin https://github.com/<your-username>/rel-dyeing-erp.git
   git push -u origin master
   ```
   (If it says a remote already exists, use `git remote set-url origin <url>` instead.)
3. Refresh the repo page on GitHub — you should see all the files.

**From now on, to publish a change:** after I commit here, you just run `git push`.

---

## Part B — One-time: set up the factory PC

1. **Install Git for Windows** from git-scm.com (it includes the credential manager). Accept the
   defaults.
2. **Sign in to GitHub** so the PC can read the private repo. Easiest way: the first time you run
   a `git clone`/`git pull` below, Windows pops up a **"Sign in to GitHub"** window — log in once
   and it's remembered. *(Alternative: create a read-only Personal Access Token on GitHub and paste
   it when git asks for a password.)*
3. **Clone the repo** to a simple location, e.g. `C:\`:
   ```
   cd C:\
   git clone https://github.com/<your-username>/rel-dyeing-erp.git REL_DYEING
   ```
   You now have `C:\REL_DYEING\mvp\` with the app.
4. **Create the secrets file** (stays only on this PC): copy `mvp\secrets.example.json` to
   `mvp\secrets.local.json`.
5. **First run:** double-click `C:\REL_DYEING\mvp\start_server.bat`. It builds the database and
   serves on `http://localhost:8080/`. (If you want your current data on the factory PC, also copy
   your `data.json` into `mvp\` before this first run — it's gitignored so it won't sync back.)
6. Log in `ADMIN` / `sonkeiwachikara`, then **change the password**.
7. Set up **auto-start on boot** and **daily backups** exactly as in `docs/DEPLOYMENT.md`.

---

## Part C — Applying updates (the everyday flow)

Whenever there's a new version on GitHub:

- **Simplest:** double-click **`mvp\update.bat`**. It runs `git pull` and restarts the server so
  backend changes take effect. Refresh the browser and you're on the new version.
- Screen-only changes (buttons, layout, colours) show up on a browser refresh even without a
  restart; `update.bat` covers everything either way.

**Optional auto-sync:** you can schedule `git pull` to run on its own (Task Scheduler → a task that
runs `git -C C:\REL_DYEING pull` every, say, 30 minutes). I'd keep updates **manual** at first so
you decide when the server restarts (a restart logs everyone out), and switch to auto later once
you're comfortable.

---

## Notes
- **Nothing sensitive syncs.** `secrets.local.json`, `data.json`, `data.sqlite`, and `backups/` are
  gitignored — they live only on each machine. GitHub only ever holds the code.
- **Keep the repo private.** The app has no HTTPS yet and the seed contains a default admin password
  (which you change on first login), so the repo should stay private.
- **Your data is safe across updates.** `git pull` only changes code; it never touches
  `data.sqlite`. Backups (Part B step 7) are your safety net regardless.
