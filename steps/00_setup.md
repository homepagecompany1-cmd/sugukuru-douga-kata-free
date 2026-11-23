# 0. 自分の非公開リポを作ってつなぐ（最初の1回だけ・スマホでできる）

## A：Claude Code の人
1. スマホのブラウザで https://github.com/homepagecompany1-cmd/sugukuru-douga-kata-free/generate を開く（GitHub にログイン）
2. 名前は何でもよい。**Private（非公開）** を選んで **Create repository**
3. Claude アプリ → **Code** タブ → リポを選ぶ → 今作ったリポ（初回は GitHub の許可画面が出るので許可）
   - 一覧に出ない時：GitHub の許可で「選んだリポだけ」にしている。GitHub の **Settings → Applications → Claude → Configure** で、作ったリポを足す（または All repositories）
4. 「AGENTS.md を読んで、始めて」と送る

## B：Codex の人
1. 上の 1〜2 と同じ
2. スマホのブラウザで chatgpt.com/codex → 設定 → 環境（Environments）→ 作成 → GitHub をつなぎ、今作ったリポを選ぶ
3. 環境の **Setup script** に `bash tools/setup.sh` と書いて保存
4. Codex で「AGENTS.md を読んで、始めて」と送る。保存は Codex が作る **PR** を GitHub で **Merge**

## AI がやること
- 非公開を確かめる → `state/PROGRESS.md` の 0 を「完了」にして保存。
