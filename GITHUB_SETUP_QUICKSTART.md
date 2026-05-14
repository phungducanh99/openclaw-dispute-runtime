# GitHub Setup Quickstart (No-Code)

## 1) Khởi tạo repo local

```bash
cd "2026 Dispute/openclaw_runtime"
git init
git branch -M main
```

## 2) Commit lần đầu

```bash
git add .
git commit -m "init: openclaw dispute runtime"
```

## 3) Nối repo GitHub

```bash
git remote add origin <GITHUB_REPO_URL>
git push -u origin main
```

Ví dụ URL:

`https://github.com/<user-or-org>/openclaw-dispute-runtime.git`

## 4) Workflow hằng ngày (Mac dev)

```bash
git checkout -b feat/<change-name>
# sửa code + test
git add .
git commit -m "feat: <short-message>"
git push -u origin feat/<change-name>
```

Sau đó tạo Pull Request trên GitHub và merge vào `main`.

## 5) Deploy lên Windows (production)

```powershell
cd C:\openclaw_runtime
git fetch --all --tags
git checkout <RELEASE_TAG>
.\stop_normal_mode.ps1
.\start_normal_mode.ps1
.\health_gate.ps1
```
